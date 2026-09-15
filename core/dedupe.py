import hashlib
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

def canonical_url(url):
    u = urlsplit(url)
    if u.scheme not in ('https', 'http') or not u.hostname:
        raise ValueError('공고 URL이 올바르지 않습니다')
    query = sorted((k, v) for k, v in parse_qsl(u.query, keep_blank_values=True)
                   if not k.lower().startswith('utm_') and k not in ('fbclid', 'gclid'))
    return urlunsplit((u.scheme.lower(), u.netloc.lower(), u.path or '/', urlencode(query), ''))

def identity(job):
    # Dates deliberately excluded: extensions must update the same record.
    return hashlib.sha256((job.company.strip()+'|'+canonical_url(job.official_url)+'|'+job.role.strip()).encode()).hexdigest()[:32]

def period_key(job):
    if not job.start or not job.deadline or not job.role:
        return None
    return (job.company.strip(), job.role.strip(), job.start, job.deadline)
