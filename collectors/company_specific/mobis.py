import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from collectors.base import Collector, SourceError, date_value
from core.models import Job, now_iso

def section(soup,name):
    heading=soup.select_one('p.tit.'+name)
    if not heading:return ''
    return heading.parent.get_text('\n',strip=True).removeprefix(heading.get_text(strip=True)).strip()

class Mobis(Collector):
    def collect(self):
        body,_=self.http.get(self.source['url'])
        soup=BeautifulSoup(body,'html.parser');links=soup.select('a.job-item[href^="/jobs-view?seq="]')
        if not links:raise SourceError('모비스 공고 항목 미검출')
        seen=set()
        for item in links:
            url=urljoin(self.source['url'],item['href'])
            if url in seen:continue
            seen.add(url)
            detail,changed=self.http.get(url)
            old=next((j for j in self.http.store.jobs() if j.source_url==url),None)
            if old and not changed:
                old.last_checked=now_iso();yield old;continue
            doc=BeautifulSoup(detail,'html.parser')
            title=item.select_one('.tit').get_text(' ',strip=True)
            recruitment=item.select_one('.career').get_text(' ',strip=True)
            dates=re.findall(r'20\d{2}-\d{2}-\d{2}(?: \d{2}:\d{2})?',item.select_one('.date').get_text(' ',strip=True))
            requirements=section(doc,'qualify');duties=section(doc,'job');preferences=section(doc,'special')
            if not requirements or not duties:raise SourceError('모비스 지원자격/직무상세 구조 변경')
            yield Job(company=self.source['name'],title=title,role=title,official_url=url,source_url=url,source_id=self.source['id'],company_type='large',industry=self.source['industry'],recruitment=recruitment,
                duties=duties,requirements=requirements,preferences=preferences,majors='\n'.join(x for x in requirements.splitlines() if '전공' in x),
                education='\n'.join(x for x in requirements.splitlines() if re.search('학사|석사|졸업',x)),
                location=' · '.join(x.get_text(' ',strip=True) for x in item.select('.info-wrap02 p')),
                start=date_value(dates[0]) if dates else '',deadline=date_value(dates[-1],True) if len(dates)>1 else '',detail_complete=True)
