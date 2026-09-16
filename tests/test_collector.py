import unittest
import tempfile
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import yaml
from core.models import Job
from core.filters import classify
from core.storage import Storage
from core.export import export_feed
from collectors.base import date_value
from collectors.company_specific.lgcareers import LGCareers
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

if __name__=='__main__':unittest.main()
