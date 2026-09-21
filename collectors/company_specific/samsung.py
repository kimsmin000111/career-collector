import json
from datetime import datetime
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from collectors.base import Collector, SourceError
from core.models import Job, KST


def clean(value):
    return str(value or '').strip()


def compact_date(value):
    value=clean(value)
    for pattern in ('%Y%m%d%H%M','%Y%m%d'):
        try:
            return datetime.strptime(value,pattern).replace(tzinfo=KST).isoformat()
        except ValueError:
            pass
    return ''


class Samsung(Collector):
    """Samsung Careers public list/detail data, limited to new-hire and intern notices."""
    def collect(self):
        s=self.source
        page=1
        while True:
            payload=[
                ('currentPageNo',str(page)),('intNo','0'),('strVal',''),('strTxt',''),
                ('strKey',''),('strType','A'),('strType','C'),('strOrderBy','AA'),('strEntity','')
            ]
            body,_=self.http.post_form(s['list_url'],payload)
            doc=BeautifulSoup(body,'html.parser')
            counter=doc.select_one('.divCnt')
            if not counter:
                raise SourceError('삼성 채용 목록 구조 변경')
            items=doc.select('li a[data-value]')
            total=int(counter.get('data-value') or 0)
            if total and not items:
                raise SourceError('삼성 채용 목록 항목 미검출')
            for anchor in items:
                seq=''.join(ch for ch in anchor.get('data-value','') if ch.isdigit())
                if not seq:
                    continue
                body,_=self.http.get(s['detail_url']+'?seqno='+seq+'&strCode=')
                try:
                    response=json.loads(body)
                except json.JSONDecodeError:
                    raise SourceError('삼성 채용 상세 JSON 형식 오류') from None
                data=response.get('data',{}) if response.get('success') else {}
                parent=data.get('result')
                roles=data.get('items')
                if not isinstance(parent,dict) or not isinstance(roles,list):
                    raise SourceError('삼성 채용 상세 구조 변경')
                recruitment={'A':'신입','C':'인턴'}.get(parent.get('recruitType'),'확인 필요')
                common=clean(parent.get('qlfctKr'))
                for role in roles or [{}]:
                    role_name=clean(role.get('titleKr')) or clean(parent.get('title'))
                    if not role_name:
                        raise SourceError('삼성 채용 직무명 미검출')
                    requirements='\n'.join(filter(None,[common,clean(role.get('qlfctKr'))]))
                    duties='\n'.join(filter(None,[clean(role.get('taskKr')),clean(role.get('explnKr'))]))
                    majors='\n'.join(line for line in requirements.splitlines() if '전공' in line)
                    url='https://www.samsungcareers.com/hr/?no='+str(parent.get('seq') or seq)
                    yield Job(
                        company=clean(parent.get('cmpNameKr')) or s['name'],
                        title=clean(parent.get('title')),role=role_name,
                        official_url=url,source_url=url,source_id=s['id'],company_type='large',
                        external_id=f"{parent.get('seq') or seq}:{role.get('seq') or role_name}",
                        industry=s['industry'],recruitment=recruitment,
                        duties=duties,requirements=requirements,preferences='\n'.join(filter(None,[clean(role.get('favorKr')),clean(parent.get('etcKr'))])),
                        majors=majors,location=clean(role.get('workPlaceKr')),
                        employment='인턴' if recruitment=='인턴' else '정규직',
                        start=compact_date(parent.get('startdate')),deadline=compact_date(parent.get('enddate')),
                        detail_complete=bool(requirements),mixed_roles=False
                    )
            max_page=int(counter.get('data-max') or 0)
            if page>=max_page:
                return
            page+=1
            if page>s.get('max_pages',10):
                raise SourceError('삼성 채용 목록 페이지 상한 도달')
