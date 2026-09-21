import re
import json
from datetime import datetime
from bs4 import BeautifulSoup
from collectors.base import Collector, SourceError, date_value
from core.models import Job, KST

class JobAlio(Collector):
    RELEVANT_NCS=('R600009','R600014','R600015','R600016','R600017','R600019','R600023','R600025')

    def collect(self):
        """Use the Ministry's public ALIO JSON list instead of scraping every detail page."""
        s=self.source;records={}
        page_size=s.get('page_size',100)
        for ncs in self.RELEVANT_NCS:
            for page in range(1,s.get('max_pages',10)+1):
                payload=[('pageNo',str(page)),('numOfRows',str(page_size)),('ncsCdLst',ncs),('ongoingYn','Y')]
                response,_=self.http.post_form(s['open_data_url'],payload)
                try:data=json.loads(response).get('data',{})
                except (ValueError,TypeError):raise SourceError('ALIO 공개 목록 JSON 형식 오류','PARSER_ERROR') from None
                items=data.get('result')
                if data.get('resultCode')!=200 or not isinstance(items,list):
                    raise SourceError('ALIO 공개 목록 구조 변경','PAGE_STRUCTURE_CHANGED')
                for item in items:
                    external_id=str(item.get('recrutPblntSn') or '')
                    if external_id:records[external_id]=item
                total=int(data.get('totalCount') or 0)
                if page*page_size>=total:break
            else:raise SourceError('ALIO 공개 목록 페이지 상한 도달; 일부 공고 누락 가능')
        if not records:raise SourceError('ALIO 공개 목록 미검출','SOURCE_EMPTY_ANOMALY')
        for external_id,item in sorted(records.items(),reverse=True):
            yield self.from_open_data(item,external_id)

    def from_open_data(self,item,external_id):
        s=self.source
        exact_url=f"https://job.alio.go.kr/recruitview.do?idx={external_id}"
        def compact_date(value,end=False):
            value=str(value or '')
            if not re.fullmatch(r'\d{8}',value):return ''
            point=datetime.strptime(value,'%Y%m%d').replace(
                hour=23 if end else 0,minute=59 if end else 0,second=59 if end else 0,tzinfo=KST)
            return point.isoformat()
        requirements='\n'.join(filter(None,[item.get('aplyQlfcCn'),item.get('disqlfcRsn')]))
        duties='\n'.join(filter(None,[item.get('ncsCdNmLst'),item.get('scrnprcdrMthdExpln')]))
        return Job(
            company=item.get('instNm') or s['name'],title=item.get('recrutPbancTtl',''),
            role=item.get('recrutPbancTtl',''),official_url=exact_url,source_url=exact_url,
            source_label='ALIO 공식 공개 채용정보',source_id=s['id'],
            company_type=s.get('institution_types',{}).get(item.get('instNm'),'public_institution'),
            external_id=external_id,industry='공공기관·기계 기술직',
            recruitment=item.get('recrutSeNm',''),duties=duties,requirements=requirements,
            preferences='\n'.join(filter(None,[item.get('prefCondCn'),item.get('prefCn')])),
            education=item.get('acbgCondNmLst',''),location=item.get('workRgnNmLst',''),
            employment=item.get('hireTypeNmLst',''),start=compact_date(item.get('pbancBgngYmd')),
            deadline=compact_date(item.get('pbancEndYmd'),True),detail_complete=bool(requirements),mixed_roles=True)

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
