from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))
def now_iso():
    return datetime.now(KST).isoformat(timespec='seconds')

@dataclass
class Job:
    company: str
    title: str
    official_url: str
    source_id: str
    role: str = ''
    company_type: str = 'unknown'
    industry: str = ''
    recruitment: str = ''
    entry_status: str = '확인 필요'
    mechanical_status: str = '확인 필요'
    location: str = ''
    requirements: str = ''
    preferences: str = ''
    majors: str = ''
    education: str = ''
    required_certificates: str = ''
    preferred_certificates: str = ''
    employment: str = ''
    start: str = ''
    deadline: str = ''
    source_url: str = ''
    source_label: str = '공식 채용페이지'
    id: str = ''
    first_seen: str = ''
    last_checked: str = ''
    active: bool = True
    closed: bool = False
    detail_complete: bool = False
    mixed_roles: bool = False
    category: str = '기타'
    score: int = 0
    fit: str = '낮음'
    reasons: list[str] = field(default_factory=list)
    # Supporting evidence stays separate from preferred qualifications.
    duties: str = ''

    def record(self):
        return asdict(self)
