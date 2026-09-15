"""Registry-configured official JSON API. No invented JOB-ALIO API endpoint."""
import json
import os
from urllib.parse import urlencode, urlsplit, urlunsplit, parse_qsl
from .base import Collector, SourceError, date_value
from core.models import Job

def dig(data,path):
    for key in path.split('.') if path else []:
        data=data.get(key) if isinstance(data,dict) else None
    return data

class PublicAPI(Collector):
    def collect(self):
        s=self.source;api=s['api'];key=os.getenv(api.get('key_env','PUBLIC_JOBS_API_KEY'),'')
        if api.get('key_required',True) and not key:raise SourceError('공식 API 인증키 설정 필요')
        u=urlsplit(api['endpoint'])
        for page in range(1,api.get('max_pages',20)+1):
            params=dict(parse_qsl(u.query));params.update(api.get('params',{}))
            params[api.get('page_param','page')]=page
            if key:params[api.get('key_param','serviceKey')]=key
            # Do not cache API URLs containing secrets in SQLite or logs.
            r=self.http.request(urlunsplit((u.scheme,u.netloc,u.path,urlencode(params),'')))
            if r.status_code!=200:raise SourceError('공식 API HTTP '+str(r.status_code))
            try:rows=dig(r.json(),api.get('items_path','data'))
            except ValueError:raise SourceError('공식 API JSON 형식 불일치') from None
            if not isinstance(rows,list):raise SourceError('API 오류 또는 items_path 변경')
            if not rows:return
            for row in rows:
                values={field:dig(row,path) or '' for field,path in api['fields'].items()}
                values['company']=values.get('company') or s['name']
                values['source_id']=s['id'];values['source_label']=s.get('source_label','공식 공공데이터 API')
                values['source_url']=values.get('official_url','')
                values['company_type']=s.get('institution_types',{}).get(values['company'],s.get('record_type','unknown'))
                values['industry']=s.get('industry','공공기관 기술직')
                values['start']=date_value(str(values.get('start','')))
                values['deadline']=date_value(str(values.get('deadline','')),True)
                values['detail_complete']=bool(values.get('requirements')) and api.get('single_role',False)
                values['mixed_roles']=not api.get('single_role',False)
                if not values.get('official_url') or not values.get('title'):raise SourceError('API 공식 URL/제목 누락')
                yield Job(**values)
        raise SourceError('API 페이지 상한 도달; 부분 수집')
