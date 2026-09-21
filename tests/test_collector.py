import unittest
import tempfile
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import yaml
from core.models import Job
from core.filters import classify
from core.storage import Storage
from core.export import export_feed
from collectors.base import date_value
from core.dedupe import canonical_url
from collectors.company_specific.lgcareers import LGCareers
from collectors.company_specific.jobalio import JobAlio
from collectors.company_specific.hanwha import Hanwha
from collectors.company_specific.samsung import Samsung
CFG=yaml.safe_load((Path(__file__).resolve().parents[1]/'config/keywords.yaml').read_text(encoding='utf-8'))

def job(**kw):
    values=dict(company='시험기업',title='기계설계',role='기계설계',official_url='https://example.com/jobs/1',source_id='test',company_type='large',recruitment='신입',requirements='기계공학 학사',majors='기계공학',detail_complete=True)
    values.update(kw);return Job(**values)

class Rules(unittest.TestCase):
    def test_experience_overrides_title(self):
        self.assertEqual(classify(job(title='신입/경력',requirements='관련 실무경력 2년 이상'),CFG).entry_status,'지원 어려움')
    def test_preference_not_mandatory(self):
        self.assertEqual(classify(job(requirements='기졸업자\n경력 2년 이상 우대'),CFG).entry_status,'지원 가능')
    def test_mixed_roles_never_false_positive(self):
        self.assertEqual(classify(job(mixed_roles=True,requirements='A 신입\nB 경력 3년 이상'),CFG).entry_status,'확인 필요')
    def test_experienced_contract_does_not_become_candidate(self):
        self.assertEqual(classify(job(recruitment='경력',employment='계약직'),CFG).entry_status,'지원 어려움')
    def test_missing_detail(self):
        self.assertEqual(classify(job(detail_complete=False),CFG).entry_status,'확인 필요')
    def test_unknown_size(self):
        self.assertEqual(classify(job(company_type='unknown'),CFG).entry_status,'확인 필요')
    def test_business_role_not_mechanical(self):
        self.assertEqual(classify(job(title='재무회계',role='회계',majors='경영학',requirements='회계학 학사'),CFG).mechanical_status,'관련 없음')
    def test_missing_mechanical_keyword_can_be_candidate(self):
        self.assertEqual(classify(job(title='제품개발',role='제품개발',majors='공학',requirements='공학 학사'),CFG).mechanical_status,'확인 필요')
    def test_incidental_single_keyword_in_duties_is_not_mechanical(self):
        self.assertEqual(classify(job(title='프론트',role='고객응대',majors='전공무관',duties='사내 스터디에서 로봇 주제를 다룹니다'),CFG).mechanical_status,'관련 없음')
    def test_two_independent_duty_signals_are_mechanical(self):
        self.assertEqual(classify(job(title='엔지니어',role='기술지원',majors='공학',duties='자동화 설비의 유지보수를 담당합니다'),CFG).mechanical_status,'관련 있음')
    def test_single_broad_business_word_is_not_mechanical(self):
        self.assertEqual(classify(job(title='경영관리',role='재무',majors='상경계열',duties='내부 회계관리제도를 운영 평가합니다'),CFG).mechanical_status,'관련 없음')
    def test_two_broad_duty_signals_remain_for_review(self):
        self.assertEqual(classify(job(title='광학',role='광학',majors='이공계',duties='제품 시험과 품질 분석을 담당합니다'),CFG).mechanical_status,'확인 필요')
    def test_deadline_timezone(self):
        self.assertEqual(date_value('2026.09.15 15:00',True),'2026-09-15T15:00:00+09:00')
    def test_canonical_url_removes_tracking_but_keeps_job_identity(self):
        url=canonical_url('https://example.com/hr/?utm_source=x&no=23046&rtSeq=77')
        self.assertNotIn('utm_source',url)
        self.assertIn('no=23046',url)
        self.assertIn('rtSeq=77',url)

class DurableStorage(unittest.TestCase):
    def test_identity_extensions_role_changes_and_distinct_postings(self):
        with tempfile.TemporaryDirectory() as t:
            s=Storage(Path(t)/'jobs.db')
            a=classify(job(start='2026-09-01T00:00:00+09:00',deadline='2099-09-20T10:00:00+09:00'),CFG)
            self.assertEqual(s.upsert(a),'new');identity=a.id
            self.assertEqual(s.upsert(a),'unchanged')
            a.deadline='2099-09-25T10:00:00+09:00';self.assertEqual(s.upsert(a),'changed')
            b=classify(job(official_url='https://example.com/jobs/2',start=a.start,deadline=a.deadline,recruitment='경력'),CFG)
            self.assertEqual(s.upsert(b),'new');self.assertEqual(len(s.jobs()),2)
            a.role='기구설계';self.assertEqual(s.upsert(a),'changed');self.assertEqual(a.id,identity)
            s.close()
    def test_deadlines_are_not_erased_on_partial_parse(self):
        with tempfile.TemporaryDirectory() as t:
            s=Storage(Path(t)/'jobs.db');a=job(deadline='2099-09-20T10:00:00+09:00');s.upsert(a)
            b=job();s.upsert(b);self.assertEqual(s.jobs()[0].deadline,a.deadline);s.close()
    def test_expiry_keeps_history_and_no_change_export(self):
        with tempfile.TemporaryDirectory() as t:
            s=Storage(Path(t)/'jobs.db');a=job(deadline='2000-01-01T00:00:00+09:00');s.upsert(a)
            self.assertFalse(s.jobs()[0].active);self.assertEqual(len(s.jobs()),1)
            path=Path(t)/'jobs.json';self.assertTrue(export_feed(s,path,True));before=path.read_bytes()
            self.assertFalse(export_feed(s,path,False));self.assertEqual(path.read_bytes(),before);s.close()
    def test_source_health_tracks_counts_failures_and_recovery(self):
        with tempfile.TemporaryDirectory() as t:
            s=Storage(Path(t)/'jobs.db')
            first=s.source_result('source','ok',count=12)
            self.assertEqual(first['last_count'],12)
            failed=s.source_result('source','error','timeout',0,'TIMEOUT')
            self.assertEqual(failed['last_count'],12)
            self.assertEqual(failed['consecutive_failures'],1)
            self.assertEqual(failed['error_kind'],'TIMEOUT')
            recovered=s.source_result('source','ok',count=10)
            self.assertEqual(recovered['previous_count'],12)
            self.assertEqual(recovered['consecutive_failures'],0)
            s.close()

class LGCareersParsing(unittest.TestCase):
    def test_splits_one_notice_into_sector_jobs(self):
        class Http:
            def post_json(self,url,payload):
                if 'List' in url:
                    return {'status':'S','data':{'listCount':1,'jobNoticeList':[{'jobNoticeId':7,'noticeStatus':'POSTING','careerTypeName':'신입','companyName':'LG시험','jobNoticeName':'신입채용'}]}},True
                return {'status':'S','data':{'jobNoticesDetail':{'jobNoticesDetail':{'jobNoticeId':7,'jobNoticeName':'신입채용','companyName':'LG시험','careerTypeName':'신입','recStartDate':'2026.09.01 09:00','recEndDate':'2099.09.30 17:00','qualForAppInfo':'기졸업자 또는 졸업예정자','workLocation':'서울'},'recList':[{'recSectorId':1,'orgName':'생산','jobGroupName':'기구설계','detailContext':'제품 구조 설계','mainTask':'구조해석','majorCodeName':'기계공학','requiredItem':'학사','preferredItem':'기사 우대','locationName':'창원'},{'recSectorId':2,'orgName':'생산','jobGroupName':'자동화','detailContext':'설비 자동화','mainTask':'시운전','majorCodeName':'기계공학','requiredItem':'학사','preferredItem':'','locationName':'평택'}]}}},True
        source={'id':'lgcareers','name':'LG그룹','industry':'전자·가전','list_api':'https://api.example/List','detail_api':'https://api.example/Detail'}
        jobs=list(LGCareers(source,Http()).collect())
        self.assertEqual(len(jobs),2)
        self.assertNotEqual(jobs[0].official_url,jobs[1].official_url)
        self.assertEqual(jobs[0].role,'생산 · 기구설계')
        self.assertEqual(jobs[0].deadline,'2099-09-30T17:00:00+09:00')

class JobAlioCollection(unittest.TestCase):
    def test_uses_official_open_data_and_deduplicates_ncs_results(self):
        class Http:
            forms=[]
            def post_form(self,url,payload):
                self.forms.append(payload)
                item={'recrutPblntSn':304569,'instNm':'한국교통안전공단','recrutPbancTtl':'부산본부 기간제근로자 채용',
                      'recrutSeNm':'신입','aplyQlfcCn':'자동차정비기사','prefCn':'한국사 우대',
                      'acbgCondNmLst':'학력무관','workRgnNmLst':'부산','hireTypeNmLst':'청년인턴(체험형)',
                      'ncsCdNmLst':'기계','pbancBgngYmd':'20260907','pbancEndYmd':'20990922'}
                return json.dumps({'data':{'result':[item],'resultCode':200,'totalCount':1}}),True
        http=Http();source={'id':'jobalio','name':'JOB-ALIO','open_data_url':'https://opendata.alio.go.kr/list','max_pages':5,'page_size':100,'institution_types':{}}
        jobs=list(JobAlio(source,http).collect())
        self.assertEqual(len(jobs),1)
        self.assertIn('304569',jobs[0].official_url)
        self.assertEqual(jobs[0].location,'부산')
        self.assertEqual(jobs[0].deadline,'2099-09-22T23:59:59+09:00')
        self.assertEqual(classify(jobs[0],CFG).mechanical_status,'관련 있음')
        first=http.forms[0]
        self.assertIn(('ongoingYn','Y'),first)
        self.assertIn(('numOfRows','100'),first)
        self.assertIn(('ncsCdLst','R600009'),first)

class HanwhaCollection(unittest.TestCase):
    def test_splits_new_hire_notice_into_unit_roles(self):
        class Http:
            def post_json(self,url,payload):
                if 'search-rcrt' in url:
                    return {'success':True,'data':{'list':[{'rtSeq':77,'sdNm':'한화에어로스페이스','rtNm':'신입 채용'}],'hasNext':False}},True
                return {'success':True,'data':{'item':{
                    'rtSeq':77,'sdNm':'한화에어로스페이스','rtNm':'신입 채용',
                    'rtNrcrtYn':'Y','rtCarrYn':'N','rtIntnYn':'N','rtPermanentWorkYn':'Y','rtTempWorkYn':'N',
                    'rtAcptStrtDttm':'2026.09.01 09:00','rtAcptEndDttm':'2099.09.30 15:00',
                    'rtExmQlf':'기졸업자 또는 졸업예정자','unitDt':[
                        {'ruSeq':1,'ruNm':'기계설계','ruDtlJob':'항공엔진 구조 설계','ruRcrtPrsn':'기계공학 전공','ruWorkpl':'창원'},
                        {'ruSeq':2,'ruNm':'생산기술','ruDtlJob':'자동화 설비 시운전','ruRcrtPrsn':'공학 전공','ruWorkpl':'창원'}
                    ]}}},True
        source={'id':'hanwha','name':'한화그룹','industry':'항공·방산·기계','list_api':'https://api.example/search-rcrt','detail_api':'https://api.example/get-rcrt','max_pages':5}
        jobs=list(Hanwha(source,Http()).collect())
        self.assertEqual(len(jobs),2)
        self.assertEqual({item.role for item in jobs},{'기계설계','생산기술'})
        self.assertEqual(jobs[0].recruitment,'신입')
        self.assertTrue(jobs[0].detail_complete)
        self.assertNotEqual(jobs[0].official_url,jobs[1].official_url)

class SamsungCollection(unittest.TestCase):
    def test_splits_notice_into_jobs_and_keeps_mechanical_qualification(self):
        class Http:
            def post_form(self,url,payload):
                return '<input class="divCnt" data-value="1" data-max="1"><li><a data-value="23,046"></a></li>',True
            def get(self,url):
                return json.dumps({'success':True,'data':{'result':{
                    'seq':23046,'title':'3급 신입사원 채용','cmpNameKr':'삼성시험','recruitType':'A',
                    'startdate':'202609081000','enddate':'209909151700','qlfctKr':'졸업예정자 지원 가능'
                },'items':[{'titleKr':'공정엔지니어링직','taskKr':'공정 설비 관리','qlfctKr':'모집 전공 : 기계 관련 전공','favorKr':'기사 우대'}]}}),True
        source={'id':'samsung','name':'삼성그룹','industry':'전자·반도체','list_url':'https://example.com/list.data','detail_url':'https://example.com/detail.data','max_pages':10}
        jobs=list(Samsung(source,Http()).collect())
        self.assertEqual(len(jobs),1)
        self.assertEqual(jobs[0].company,'삼성시험')
        self.assertEqual(jobs[0].recruitment,'신입')
        self.assertIn('기계 관련 전공',jobs[0].majors)
        self.assertEqual(jobs[0].deadline,'2099-09-15T17:00:00+09:00')

if __name__=='__main__':unittest.main()
