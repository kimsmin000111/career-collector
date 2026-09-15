import time
import os
import re
from urllib.parse import urlsplit, urljoin
from urllib.robotparser import RobotFileParser
from datetime import datetime
import requests
from core.models import now_iso, KST

class SourceError(RuntimeError):
    pass

class HttpClient:
    """No browser spoofing, login automation, proxy rotation or challenge bypass."""
    def __init__(self, store, hosts, interval=2):
        self.store, self.hosts = store, set(hosts)
        self.interval, self.last, self.robots = interval, {}, {}
        self.session=requests.Session()
        self.session.headers['User-Agent']='CareerCollector/1.0 (+public recruitment personal-use; '+os.getenv('COLLECTOR_CONTACT','contact not configured')+')'
    def request(self, url, headers=None, robots=False):
        for _ in range(5):
            host=urlsplit(url).hostname
            if urlsplit(url).scheme!='https' or host not in self.hosts:
                raise SourceError('등록되지 않은 호스트 또는 HTTPS가 아닌 URL')
            if not robots:
                self.check_robots(url)
            time.sleep(max(0,self.interval-(time.monotonic()-self.last.get(host,0))))
            self.last[host]=time.monotonic()
            try:
                r=self.session.get(url,headers=headers or {},timeout=(10,30),allow_redirects=False,stream=True)
            except requests.RequestException as e:
                raise SourceError(type(e).__name__) from None
            if r.status_code in (301,302,303,307,308):
                url=urljoin(url,r.headers.get('Location',''))
                r.close()
                continue
            body=bytearray()
            for chunk in r.iter_content(65536):
                body.extend(chunk)
                if len(body)>5_000_000:
                    r.close()
                    raise SourceError('응답 크기 제한 초과')
            r._content=bytes(body)
            r._content_consumed=True
            r.close()
            return r
        raise SourceError('리다이렉트 제한 초과')
    def check_robots(self,url):
        host=urlsplit(url).hostname
        if host not in self.robots:
            r=self.request('https://'+host+'/robots.txt',robots=True)
            parser=RobotFileParser()
            if r.status_code in (404,410):
                parser.parse(['User-agent: *','Allow: /'])
            elif r.status_code==200 and '<html' not in r.text.lower():
                parser.parse(r.text.splitlines())
            else:
                raise SourceError('robots.txt 확인 실패: '+str(r.status_code))
            self.robots[host]=parser
        parser=self.robots[host]
        if not parser.can_fetch('CareerCollector',url):
            raise SourceError('robots.txt 수집 금지')
        self.interval=max(self.interval,parser.crawl_delay('CareerCollector') or parser.crawl_delay('*') or 0)
    def get(self,url):
        cached=self.store.db.execute('SELECT * FROM pages WHERE url=?',(url,)).fetchone()
        headers={}
        if cached:
            if cached['etag']:headers['If-None-Match']=cached['etag']
            if cached['modified']:headers['If-Modified-Since']=cached['modified']
        r=self.request(url,headers)
        if r.status_code==304 and cached:
            return cached['body'],False
        if r.status_code!=200:
            raise SourceError('HTTP '+str(r.status_code))
        # requests defaults text/html without charset to Latin-1; inspect bytes instead.
        encoding=r.encoding if r.encoding and r.encoding.lower()!='iso-8859-1' else 'utf-8'
        try:body=r.content.decode(encoding)
        except UnicodeDecodeError:body=r.content.decode('cp949',errors='replace')
        if re.search(r'captcha|verify you are human|access denied',body[:10000],re.I):
            raise SourceError('접근 제한 응답; 우회하지 않음')
        self.store.db.execute('INSERT INTO pages VALUES (?,?,?,?,?) ON CONFLICT(url) DO UPDATE SET etag=excluded.etag,modified=excluded.modified,body=excluded.body,checked_at=excluded.checked_at',(url,r.headers.get('ETag'),r.headers.get('Last-Modified'),body,now_iso()))
        self.store.db.commit()
        return body,not cached or body!=cached['body']

def date_value(value, end=False):
    m=re.search(r'(20\d{2})[.\-/](\d{1,2})[.\-/](\d{1,2})(?:\s+(\d{1,2}):(\d{2}))?',str(value))
    if not m:return ''
    y,mo,d,h,mi=m.groups()
    return datetime(int(y),int(mo),int(d),int(h or (23 if end else 0)),int(mi or (59 if end else 0)),59 if end and not h else 0,tzinfo=KST).isoformat()

class Collector:
    def __init__(self,source,http):
        self.source,self.http=source,http
    def collect(self):
        raise NotImplementedError
