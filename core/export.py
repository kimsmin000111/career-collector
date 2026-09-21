import json
from pathlib import Path

TYPES={'large':'대기업','mid':'중견기업','public_enterprise':'공기업','public_institution':'공공기관','unknown':'규모 확인 필요','small':'중소기업'}
def site_job(j):
    return dict(id=j.id,company=j.company,role=j.role or j.title,category=j.category,sector=j.industry,
        location=j.location or '원문 확인',level=j.recruitment or '확인 필요',size=TYPES.get(j.company_type,'규모 확인 필요'),
        deadline=j.deadline,start=j.start,sourceUrl=j.official_url,sourceLabel=j.source_label,
        sourceType=j.source_type,dataConfidence=j.confidence,externalId=j.external_id,
        verification='자동 수집 · 원문 확인 권장',match=j.fit,matchReason=' / '.join(j.reasons),
        requirements=j.requirements or '지원자격 상세 확인 필요',caution='규칙 기반 분류이며 개인별 지원자격 충족을 보증하지 않습니다.'+( ' 마감 시각이 원문에 없으면 해당일 종료 시각으로 표시합니다.' if j.deadline.endswith('23:59:59+09:00') else ''),
        tags=[j.entry_status,j.fit],checkedAt=j.last_checked,defaultStatus='검토전',
        eligibility=j.entry_status,mechanicalStatus=j.mechanical_status,active=j.active,
        preferences=j.preferences,majors=j.majors,education=j.education,employment=j.employment,
        requiredCertificates=j.required_certificates,preferredCertificates=j.preferred_certificates,
        duties=j.duties,firstSeen=j.first_seen,score=j.score)

def write_if_changed(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    encoded=json.dumps(data,ensure_ascii=False,indent=2)+'\n'
    if path.exists() and path.read_text(encoding='utf-8')==encoded:return False
    temp=path.with_suffix('.tmp');temp.write_text(encoded,encoding='utf-8');temp.replace(path)
    return True

def export_feed(store,path,changed):
    previous=json.loads(Path(path).read_text(encoding='utf-8')) if Path(path).exists() else {}
    jobs=[site_job(j) for j in store.jobs()]
    # Check timestamps are internal state; do not publish an identical feed every day.
    old={j['id']:j for j in previous.get('jobs',[])}
    if not changed and set(old)=={j['id'] for j in jobs}:return False
    from .models import now_iso
    return write_if_changed(path,{'schemaVersion':1,'checkedAt':now_iso(),'checkSummary':'Python 공식 채용정보 수집 결과. 지원자격·마감 시각은 원문에서 최종 확인하세요.','jobs':jobs})
