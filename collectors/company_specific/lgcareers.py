import re
from bs4 import BeautifulSoup
from collectors.base import Collector, SourceError, date_value
from core.models import Job


def text(value):
    if not value:
        return ''
    return BeautifulSoup(str(value),'html.parser').get_text('\n',strip=True)


class LGCareers(Collector):
    """LG Careers public job list/detail API, split into individual recruitment sectors."""
    def collect(self):
        payload={
            'lnbSearch':'','hashTagText':'','recDate':'CREATION_DATE','order':'DESC',
            'careerList':[],'companyCodeList':[],'desireLocList':[],'jobGroupList':[]
        }
        response,_=self.http.post_json(self.source['list_api'],payload)
        if response.get('status')!='S' or not isinstance(response.get('data',{}).get('jobNoticeList'),list):
            raise SourceError('LG Careers 목록 구조 변경')
        notices=response['data']['jobNoticeList']
        if response['data'].get('listCount',len(notices)) and not notices:
            raise SourceError('LG Careers 공고 항목 미검출')
        allowed={'신입','신입/경력','인턴'}
        for summary in notices:
            if summary.get('noticeStatus')!='POSTING' or summary.get('careerTypeName') not in allowed:
                continue
            notice_id=summary.get('jobNoticeId')
            detail_response,_=self.http.post_json(self.source['detail_api'],{'jobNoticeId':notice_id})
            if detail_response.get('status')!='S':
                raise SourceError('LG Careers 상세 조회 실패')
            wrapper=detail_response.get('data',{}).get('jobNoticesDetail',{})
            parent=wrapper.get('jobNoticesDetail')
            sectors=wrapper.get('recList')
            if not isinstance(parent,dict) or not isinstance(sectors,list) or not sectors:
                raise SourceError('LG Careers 상세 구조 변경')
            common_requirements=text(parent.get('qualForAppInfo'))
            recruitment=parent.get('careerTypeName') or summary.get('careerTypeName','')
            start=date_value(parent.get('recStartDate',''))
            deadline=date_value(parent.get('recEndDate',''),True)
            for sector in sectors:
                role=' · '.join(x for x in [text(sector.get('orgName')),text(sector.get('jobGroupName')),text(sector.get('jobCodeName'))] if x)
                if not role:
                    raise SourceError('LG Careers 직무명 미검출')
                sector_id=sector.get('recSectorId')
                url=f"https://careers.lg.com/apply/detail?id={notice_id}&sector={sector_id}"
                required=text(sector.get('requiredItem'))
                requirements='\n'.join(x for x in [common_requirements,required] if x)
                employment='인턴' if recruitment=='인턴' else ('계약직' if re.search(r'계약직',parent.get('jobNoticeName','')) else '정규직')
                yield Job(
                    company=parent.get('companyName') or summary.get('companyName') or self.source['name'],
                    title=parent.get('jobNoticeName') or summary.get('jobNoticeName',''),role=role,
                    official_url=url,source_url=url,source_id=self.source['id'],company_type='large',
                    external_id=f'{notice_id}:{sector_id}',
                    industry=self.source['industry'],recruitment=recruitment,
                    duties='\n'.join(x for x in [text(sector.get('detailContext')),text(sector.get('mainTask'))] if x),
                    requirements=requirements,preferences=text(sector.get('preferredItem')),
                    majors=text(sector.get('majorCodeName')),
                    education='\n'.join(line for line in common_requirements.splitlines() if re.search(r'학사|석사|박사|졸업|학위',line)),
                    employment=employment,location=text(sector.get('locationName')) or text(parent.get('workLocation')),
                    start=start,deadline=deadline,detail_complete=bool(common_requirements and 'requiredItem' in sector)
                )
