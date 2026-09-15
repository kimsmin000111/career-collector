from urllib.parse import urljoin
from bs4 import BeautifulSoup
from .base import Collector, SourceError, date_value
from core.models import Job

def text(node,selector):
    found=node.select_one(selector) if selector else None
    return found.get_text('\n',strip=True) if found else ''

class GenericHTML(Collector):
    def collect(self):
        s=self.source
        selectors=s.get('selectors',{})
        if not selectors.get('item') or not selectors.get('link'):
            raise SourceError('HTML selector 설정 필요')
        url=s['url']; seen=set()
        for page in range(s.get('max_pages',5)):
            body,_=self.http.get(url); soup=BeautifulSoup(body,'html.parser')
            items=soup.select(selectors['item'])
            if not items and not (selectors.get('empty') and soup.select_one(selectors['empty'])):
                raise SourceError('공고 항목 미검출; 구조 변경 또는 JavaScript 확인 필요')
            for item in items:
                a=item.select_one(selectors['link']) if selectors['link']!='self' else item
                if not a or not a.get('href'):continue
                link=urljoin(url,a['href'])
                if link in seen:continue
                seen.add(link)
                detail,changed=self.http.get(link)
                old=next((j for j in self.http.store.jobs() if j.source_id==s['id'] and j.source_url==link),None)
                if old and not changed:
                    from core.models import now_iso
                    old.last_checked=now_iso(); yield old;continue
                doc=BeautifulSoup(detail,'html.parser'); fields=s.get('detail_selectors',{})
                values={k:text(doc,v) for k,v in fields.items() if k in Job.__dataclass_fields__}
                values['title']=values.get('title') or text(item,selectors.get('title'))
                if not values['title']:raise SourceError('공고 제목 추출 실패')
                values['role']=values.get('role') or values['title']
                values['start']=date_value(values.get('start',''))
                values['deadline']=date_value(values.get('deadline',''),True)
                values['detail_complete']=bool(values.get('requirements')) and s.get('single_role',False)
                values['mixed_roles']=not s.get('single_role',False)
                yield Job(company=s['name'],official_url=link,source_url=link,source_id=s['id'],company_type=s.get('type','unknown'),industry=s.get('industry',''),**values)
            next_node=soup.select_one(selectors['next']) if selectors.get('next') else None
            if not next_node or not next_node.get('href'):return
            next_url=urljoin(url,next_node['href'])
            if next_url==url:return
            url=next_url
        raise SourceError('페이지 상한 도달; 부분 수집, max_pages 검토 필요')
