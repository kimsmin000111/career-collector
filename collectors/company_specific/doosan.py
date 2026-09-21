import re
from datetime import datetime
from urllib.parse import urlencode

from bs4 import BeautifulSoup

from collectors.base import Collector, SourceError, date_value
from core.models import Job, KST


class Doosan(Collector):
    """Career Doosan public list/detail pages."""

    def collect(self):
        s=self.source
        body,_=self.http.get(s['url'])
        soup=BeautifulSoup(body,'html.parser')
        links=soup.select('ul.submenu-list3 a[onclick*="goDetail"]')
        if not links:
            raise SourceError('두산 채용 목록 구조 변경','PAGE_STRUCTURE_CHANGED')
        yielded=0
        today=datetime.now(KST).date()
        for link in links:
            match=re.search(r"goDetail\('([^']+)',\s*'([^']+)',\s*'([^']+)',\s*'([^']+)'",link.get('onclick',''))
            if not match:
                continue
            rec_id,rec_mgt,rec_type,company_code=match.groups()
            title_node=link.select_one('.f-blue')
            title=title_node.get_text(' ',strip=True) if title_node else ''
            parts=[x.strip() for x in link.stripped_strings if x.strip() and x.strip()!='|']
            dates=re.findall(r'20\d{2}-\d{2}-\d{2}',link.get_text(' ',strip=True))
            company=parts[1] if len(parts)>1 else s['name']
            recruitment=parts[-1] if parts else ''
            if not title or len(dates)<2:
                continue
            deadline=date_value(dates[-1],True)
            if deadline and datetime.fromisoformat(deadline).date()<today:
                continue
            if rec_type=='C_REC_TYPE_02' or recruitment=='경력':
                continue
            # The specialist/contract tab is not assumed to allow graduates unless the title says intern/new hire.
            if rec_type=='C_REC_TYPE_05' and not re.search(r'신입|인턴',title):
                continue
            query=urlencode({'MENU_ID':'RecList','PRE_URL':'REC','REC_ID':rec_id,'REC_MGT_CD':rec_mgt,
                             'REC_TYPE_CD':rec_type,'mode':'goDetail','q_COMP_CD':company_code})
            url=s['detail_base']+'?'+query
            detail,_=self.http.get(url)
            page=BeautifulSoup(detail,'html.parser')
            content=page.select_one('.content_area') or page.select_one('#contents') or page
            detail_text=content.get_text('\n',strip=True)[:38000]
            if not detail_text:
                raise SourceError('두산 채용 상세 구조 변경','PAGE_STRUCTURE_CHANGED')
            yielded+=1
            yield Job(company=company,title=title,role=title,official_url=url,source_url=url,
                source_label='Career Doosan 공식 공고',source_id=s['id'],company_type='large',
                external_id=rec_id,industry=s['industry'],recruitment='신입' if rec_type=='C_REC_TYPE_01' else recruitment,
                requirements=detail_text,duties=detail_text,employment='정규직' if rec_type=='C_REC_TYPE_01' else recruitment,
                start=date_value(dates[0]),deadline=deadline,detail_complete=True,mixed_roles=True)
        # A valid list may contain only career or already closed postings; that is a healthy zero.
        if yielded==0 and not any(re.search(r'신입|인턴',a.get_text(' ',strip=True)) for a in links):
            return
