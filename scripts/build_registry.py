"""One-time bootstrap from the existing site's public company directory."""
import json
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[1]
existing=json.loads((ROOT.parent/'career-hub/data/jobs.json').read_text(encoding='utf-8'))
sources=[dict(id='mobis',name='현대모비스',type='large',industry='로봇·자동화·모빌리티',url='https://careers.mobis.com/jobs',method='mobis',api=False,javascript=False,enabled=True,terms_reviewed=True,policy_url='https://careers.mobis.com/robots.txt',policy_note='2026-09-15 robots Allow / 확인. 이메일 수집 금지 준수; 이메일·지원자 데이터 수집하지 않음.',allowed_hosts=['careers.mobis.com'],selectors={},last_success=None),
dict(id='jobalio',name='JOB-ALIO',type='public_institution',industry='공공기관 기술직',url='https://job.alio.go.kr/recruit.do',method='jobalio',api=False,javascript=False,enabled=True,terms_reviewed=True,policy_url='https://job.alio.go.kr/right.do',allowed_hosts=['job.alio.go.kr'],max_pages=5,weekly_max_pages=30,selectors={},last_success=None,institution_types={'한국토지주택공사':'public_enterprise','한국전력공사':'public_enterprise','한국수력원자력':'public_enterprise','한국가스공사':'public_enterprise','한국지역난방공사':'public_enterprise','한국철도공사':'public_enterprise','한국도로공사':'public_enterprise','한국공항공사':'public_enterprise','인천국제공항공사':'public_enterprise','한국수자원공사':'public_enterprise','한국중부발전':'public_enterprise','한국남동발전':'public_enterprise','한국남부발전':'public_enterprise','한국동서발전':'public_enterprise','한국서부발전':'public_enterprise'})]
known={s['name'] for s in sources}
types={'대기업':'large','중견기업':'mid','공기업':'public_enterprise','공공기관':'public_institution'}
from urllib.parse import urlsplit
for c in existing['companies']:
    if c['name'] in known:continue
    known.add(c['name'])
    sources.append(dict(id='company-'+str(len(sources)),name=c['name'],type=types.get(c['size'],'unknown'),industry=c['sector'],url=c['url'],method='generic_html',api=False,javascript=None,enabled=False,terms_reviewed=False,allowed_hosts=[urlsplit(c['url']).hostname],selectors={},last_success=None,note='기존 후보 목록. 정책·목록/상세 selector 또는 공식 API 확인 전 자동 수집 안 함.'))
private='삼성전자|삼성전기|삼성SDI|현대자동차|기아|SK하이닉스|SK이노베이션|LG전자|LG화학|LG에너지솔루션|포스코|한화에어로스페이스|HD현대중공업|두산에너빌리티|LS일렉트릭|LIG넥스원|현대로템|한국항공우주산업(KAI)|효성중공업|OCI|롯데케미칼|GS칼텍스|코오롱인더스트리|금호석유화학|DN솔루션즈|SNT다이내믹스|세아베스틸|동국제강|풍산|현대엘리베이터|한미반도체|원익IPS|주성엔지니어링|유진테크|SEMES'
public='한국전력공사|한국수력원자력|한국가스공사|한국지역난방공사|한국중부발전|한국남동발전|한국남부발전|한국동서발전|한국서부발전|한국철도공사|한국도로공사|한국공항공사|인천국제공항공사|한국수자원공사|한국토지주택공사|한국환경공단|한국산업안전보건공단|한국에너지공단|한국전기안전공사|한국가스안전공사|한국교통안전공단'
for name in (private+'|'+public).split('|'):
    if name in known:continue
    sources.append(dict(id='candidate-'+str(len(sources)),name=name,type='public_enterprise' if name in sources[1]['institution_types'] else 'public_institution' if name in public.split('|') else 'unknown',industry='기계 관련 기술직',url='https://job.alio.go.kr/recruit.do' if name in public.split('|') else '',method='registry_candidate',api=False,javascript=None,enabled=False,terms_reviewed=False,allowed_hosts=[],selectors={},last_success=None,note='JOB-ALIO 통합 출처에서 기관명으로 발견 가능. 기관별 URL 확인 필요.' if name in public.split('|') else '공식 채용 URL·중견 이상 규모 근거·수집 정책 확인 필요. 등록만으로 수집 성공을 뜻하지 않음.'))
(ROOT/'config/companies.yaml').write_text(yaml.safe_dump({'sources':sources},allow_unicode=True,sort_keys=False),encoding='utf-8')
print(len(sources),'registry entries; 2 enabled sources')
