import re
from datetime import datetime, timedelta
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from collectors.base import Collector, SourceError, date_value
from core.models import Job, now_iso, KST

class JobAlio(Collector):
    RELEVANT_NCS=('R600009','R600014','R600015','R600016','R600017','R600019','R600023','R600025')

    def collect(self):
        s=self.source;seen=set();urls=set();complete=False
        today=datetime.now(KST).date()
        since=today-timedelta(days=s.get('lookback_days',365))
        for page in range(1,s.get('max_pages',80)+1):
            payload=[
                ('pageNo',str(page)),('pageSet','50'),('s_date',since.isoformat()),
                ('e_date',today.isoformat()),('ing','2'),('order','REG_DATE'),('sort','DESC')
            ]+[('detail_code',code) for code in self.RELEVANT_NCS]
            body,_=self.http.post_form(s['url'],payload)
            soup=BeautifulSoup(body,'html.parser')
            current={urljoin(s['url'],'/recruitview.do?idx='+x['value']) for x in soup.select('input[name="idxs"][value]') if x['value'].isdigit()}
            if not current:
                if page==1:raise SourceError('JOB-ALIO 목록 미검출')
                complete=True;break
            if current <= seen:raise SourceError('JOB-ALIO 페이지 반복; 페이지 이동 확인 필요')
            seen.update(current)
            urls.update(current)
            pages=[int(v) for v in re.findall(r'goPage\((\d+)\)',str(soup))]
            if not pages or page>=max(pages):
                complete=True;break
        # Recheck known open jobs even when their registration is outside the lookback.
        for old in self.http.store.jobs():
            if old.source_id==s['id'] and (old.active or old.deadline and datetime.fromisoformat(old.deadline).date()>=since):
                urls.add(old.source_url)
        for url in sorted(urls):
            body,changed=self.http.get(url)
            old=next((j for j in self.http.store.jobs() if j.source_url==url),None)
            if old and not changed:
                old.last_checked=now_iso();yield old;continue
            yield self.parse(body,url)
        if not complete:raise SourceError('JOB-ALIO 관련 직군 진행 공고 페이지 상한 도달; 일부 공고 누락 가능')

    def parse(self,body,url):
        s=self.source
        doc=BeautifulSoup(body,'html.parser')
        company=doc.select_one('h2:not(.dis_hide)')
        if not company:raise SourceError('JOB-ALIO 기관명 미검출')
        table={}
        for th in doc.select('th'):
            td=th.find_next_sibling('td')
            if td:table[th.get_text(' ',strip=True)]=td.get_text('\n',strip=True)
        sections={}
        for h in doc.select('h4'):
            content=h.find_next_sibling()
            sections[h.get_text(strip=True)]=content.get_text('\n',strip=True) if content else ''
        # Title is the first non-empty text block immediately after company heading.
        title_node=company.find_next(['p','h3'])
        title=title_node.get_text(' ',strip=True) if title_node else ''
        if not title or not table.get('채용구분'):raise SourceError('JOB-ALIO 제목/채용구분 구조 변경')
        dates=re.findall(r'(?:20)?\d{2}\.\d{2}\.\d{2}',table.get('채용기간',''))
        dates=[('20'+d if len(d)==8 else d) for d in dates]
        name=company.get_text(strip=True)
        return Job(company=name,title=title,role=title,official_url=url,source_url=url,source_label='JOB-ALIO 공식 공고',source_id=s['id'],company_type=s.get('institution_types',{}).get(name,'public_institution'),industry='공공기관·기계 기술직',recruitment=table.get('채용구분',''),
            external_id=url.rsplit('=',1)[-1],
            duties=table.get('표준직무(NCS)',''),education=table.get('학력정보',''),location=table.get('근무지',''),employment=table.get('고용형태',''),
            requirements=sections.get('응시자격',''),preferences=sections.get('우대내용',''),
            start=date_value(dates[0]) if dates else '',deadline=date_value(dates[-1],True) if len(dates)>1 else '',
            detail_complete=bool(sections.get('응시자격')),mixed_roles=True)
