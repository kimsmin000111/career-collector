import re
from bs4 import BeautifulSoup
from collectors.base import Collector, SourceError, date_value
from core.models import Job


def text(value):
    if not value:
        return ''
    return BeautifulSoup(str(value),'html.parser').get_text('\n',strip=True)


class Hanwha(Collector):
    """Hanwha's public recruitment API, split into each advertised unit role."""
    def collect(self):
        s=self.source
        summaries={}
        for flag in ('rtNrcrtYn','rtIntnYn'):
            page=0
            while True:
                payload={
                    'langCd':'ko','searchText':'','sdSeqList':None,
                    'rtNrcrtYn':'','rtCarrYn':'','rtIntnYn':'',
                    'rtPermanentWorkYn':'','rtTempWorkYn':'',
                    'djSeqList':None,'rjSeqList':None,'page':page,'size':100
                }
                payload[flag]='Y'
                response,_=self.http.post_json(s['list_api'],payload)
                data=response.get('data',{}) if response.get('success') else {}
                items=data.get('list')
                if not isinstance(items,list):
                    raise SourceError('한화 채용 목록 구조 변경')
                for item in items:
                    if item.get('rtSeq') is not None:
                        summaries[item['rtSeq']]=item
                if not data.get('hasNext'):
                    break
                page+=1
                if page>=s.get('max_pages',5):
                    raise SourceError('한화 채용 목록 페이지 상한 도달')
        for rt_seq,summary in summaries.items():
            response,_=self.http.post_json(s['detail_api'],{'rtSeq':rt_seq,'hidnKey':None,'langCd':'ko'})
            item=response.get('data',{}).get('item') if response.get('success') else None
            if not isinstance(item,dict):
                raise SourceError('한화 채용 상세 구조 변경')
            recruitment='/'.join(label for key,label in (
                ('rtNrcrtYn','신입'),('rtCarrYn','경력'),('rtIntnYn','인턴')
            ) if item.get(key)=='Y')
            employment='/'.join(label for key,label in (
                ('rtPermanentWorkYn','정규직'),('rtTempWorkYn','계약직')
            ) if item.get(key)=='Y')
            common_requirements='\n'.join(filter(None,[text(item.get('rtExmQlf')),text(item.get('rtRctPrd'))]))
            common_detail='\n'.join(filter(None,[text(item.get('rtMdeCont')),text(item.get('rtEct'))]))
            units=item.get('unitDt') or [{}]
            for unit in units:
                role=text(unit.get('ruNm')) or item.get('rtNm') or summary.get('rtNm','')
                if not role:
                    raise SourceError('한화 채용 직무명 미검출')
                unit_id=unit.get('ruSeq') or 'notice'
                url=f"https://www.hanwhain.com/portal/apply/recruit/detail?rtSeq={rt_seq}#unit-{unit_id}"
                unit_requirements=text(unit.get('ruRcrtPrsn'))
                requirements='\n'.join(filter(None,[common_requirements,unit_requirements]))
                duties='\n'.join(filter(None,[text(unit.get('ruDtlJob')),common_detail]))
                yield Job(
                    company=item.get('sdNm') or summary.get('sdNm') or s['name'],
                    title=item.get('rtNm') or summary.get('rtNm',''),role=role,
                    official_url=url,source_url=url,source_id=s['id'],company_type='large',
                    external_id=f'{rt_seq}:{unit_id}',
                    industry=s['industry'],recruitment=recruitment,
                    duties=duties,requirements=requirements,
                    location=text(unit.get('ruWorkpl')),employment=employment,
                    start=date_value(item.get('rtAcptStrtDttm','')),
                    deadline=date_value(item.get('rtAcptEndDttm',''),True),
                    detail_complete=bool(requirements),mixed_roles=False
                )
