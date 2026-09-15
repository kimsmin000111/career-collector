import argparse
import json
import os
import sys
from pathlib import Path
from datetime import datetime
import yaml
from core.models import now_iso, KST
from core.storage import Storage
from core.filters import classify
from core.export import export_feed, write_if_changed
from collectors.base import HttpClient, SourceError
from collectors.generic_html import GenericHTML
from collectors.public_jobs import PublicAPI
from collectors.company_specific.mobis import Mobis
from collectors.company_specific.jobalio import JobAlio

ROOT=Path(__file__).resolve().parent
ADAPTERS={'generic_html':GenericHTML,'public_api':PublicAPI,'mobis':Mobis,'jobalio':JobAlio}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--mode',choices=['daily','weekly'],default='daily')
    parser.add_argument('--source',help='Only one source ID')
    parser.add_argument('--db',default=str(ROOT/'data/jobs.db'))
    parser.add_argument('--max-pages',type=int,help='Override pagination for a bounded smoke run')
    parser.add_argument('--errors',action='store_true')
    parser.add_argument('--init-only',action='store_true')
    args=parser.parse_args()
    registry=yaml.safe_load((ROOT/'config/companies.yaml').read_text(encoding='utf-8'))
    cfg=yaml.safe_load((ROOT/'config/keywords.yaml').read_text(encoding='utf-8'))
    store=Storage(args.db)
    if args.init_only:store.close();return 0
    if args.errors:
        for r in store.db.execute("SELECT id,checked_at,status,error FROM sources WHERE status!='ok'"):
            print(json.dumps(dict(r),ensure_ascii=False))
        store.close();return 0
    counts={'new':0,'changed':0};results=[];attempted=0;succeeded=0;new_ids=set()
    for original in registry['sources']:
        if args.source and original['id']!=args.source:continue
        s=dict(original)
        s['run_mode']=args.mode
        if not s.get('enabled'):
            continue
        if not s.get('terms_reviewed'):
            store.source_result(s['id'],'blocked','이용정책 검토 필요');continue
        if args.max_pages:s['max_pages']=args.max_pages
        elif args.mode=='weekly':s['max_pages']=s.get('weekly_max_pages',s.get('max_pages',5))
        attempted+=1; n=0
        try:
            client=HttpClient(store,s['allowed_hosts'],s.get('interval_seconds',2))
            for job in ADAPTERS[s['method']](s,client).collect():
                job=classify(job,cfg)
                change=store.upsert(job)
                if change in counts:counts[change]+=1
                if change=='new':new_ids.add(job.id)
                n+=1
                if args.mode=='weekly' and job.company!=s['name']:
                    store.db.execute('INSERT INTO candidates VALUES (?,?) ON CONFLICT(name) DO UPDATE SET record=excluded.record',(job.company,json.dumps({'name':job.company,'url':job.official_url,'type':job.company_type,'status':'기관별 채용 URL·정책 검토 필요'},ensure_ascii=False)))
                    store.db.commit()
            store.source_result(s['id'],'ok');succeeded+=1
            results.append({'id':s['id'],'status':'ok','records':n})
        except (SourceError,ValueError,KeyError,TypeError) as e:
            # Error messages contain no request URLs / API keys.
            message=str(e) if isinstance(e,SourceError) else type(e).__name__
            store.source_result(s['id'],'partial' if n else 'error',message)
            results.append({'id':s['id'],'status':'partial' if n else 'error','records':n,'reason':message})
        print(json.dumps(results[-1],ensure_ascii=False),flush=True)
    counts['changed']+=store.expire()
    jobs=store.jobs();now=datetime.now(KST)
    eligible=[j for j in jobs if j.active and j.entry_status!='지원 어려움' and j.mechanical_status!='관련 없음']
    within=lambda n:sum(1 for j in eligible if j.deadline and 0 <= (datetime.fromisoformat(j.deadline).date()-now.date()).days <= n)
    updated=export_feed(store,ROOT/'output/jobs.json',counts['new']+counts['changed']>0)
    metrics={'신규 공고 수':counts['new'],'변경 공고 수':counts['changed'],
        '신규 지원 가능 공고 수':sum(1 for j in jobs if j.id in new_ids and j.entry_status=='지원 가능' and j.mechanical_status=='관련 있음'),
        '확인 필요 공고 수':sum(j.entry_status=='확인 필요' or j.mechanical_status=='확인 필요' for j in eligible),
        '7일 이내 마감 공고 수':within(7),'3일 이내 마감 공고 수':within(3),'오늘 사이트 업데이트 여부':updated}
    health={'checkedAt':now_iso(),'mode':args.mode,'attempted':attempted,'succeeded':succeeded,'sources':results,'metrics':metrics}
    write_if_changed(ROOT/'output/health.json',health)
    write_if_changed(ROOT/'logs'/f'{now.date()}-{args.mode}.json',metrics)
    if args.mode=='weekly':
        write_if_changed(ROOT/'output/source-candidates.json',[json.loads(r['record']) for r in store.db.execute('SELECT record FROM candidates')])
    summary=os.getenv('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary,'a',encoding='utf-8') as f:
            f.write('## 채용공고 수집\n\n'+ '\n'.join(f'- {k}: {v}' for k,v in metrics.items())+'\n\n')
            for r in results:
                if r['status'] in ('partial','error'):f.write(f"- {r['id']}: {r['status']} — {r.get('reason','')}\n")
    print(json.dumps(metrics,ensure_ascii=False))
    store.close()
    # Preserve and publish healthy-source data when one official site is temporarily unavailable.
    # A run is failed only when there was nothing to check or every active source failed.
    return 2 if not attempted or not succeeded else 0

if __name__=='__main__':sys.exit(main())
