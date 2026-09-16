import re

def contains(text, words):
    return any(w.casefold() in text.casefold() for w in words)

def classify(job, cfg):
    job.reasons = []
    detail = '\n'.join([job.requirements, job.majors, job.education])
    evidence = '\n'.join([job.role, job.title, job.duties, job.majors])
    headline_evidence = '\n'.join([job.role, job.title, job.majors])
    mandatory = '\n'.join(line for line in detail.splitlines() if not re.search(r'우대|가점|선호', line))
    experience = any(re.search(p, mandatory, re.I) for p in cfg['experience_patterns'])
    senior_only = bool(re.search(r'(선임|책임|팀장|관리자)\s*(급|채용|모집)', job.title))
    explicit = contains(job.recruitment+' '+mandatory, cfg['entry_keywords'])
    experienced_only = ('경력' in job.recruitment and not contains(job.recruitment, cfg['entry_keywords'])) or bool(re.search(r'경력직\s*(전용|채용|모집)', job.title))
    if experienced_only:
        job.entry_status = '지원 어려움'
        job.reasons.append('경력 전용 모집')
    elif job.mixed_roles:
        job.entry_status = '확인 필요'
        job.reasons.append('여러 직무의 요건이 함께 있어 직무별 신입 요건 확인 필요')
    elif experience or senior_only or experienced_only:
        job.entry_status = '지원 어려움'
        job.reasons.append('필수 실무경력 또는 경력 전용 모집 근거 확인')
    elif not job.detail_complete:
        job.entry_status = '확인 필요'
        job.reasons.append('상세 지원자격 미확인')
    elif explicit or '인턴' in job.employment:
        job.entry_status = '지원 가능'
        job.reasons.append('신입 지원 근거 확인 — 개인별 필수 자격 충족을 보증하지 않음')
    else:
        job.entry_status = '확인 필요'
        job.reasons.append('필수 경력 표현이 없다는 이유만으로 신입 가능으로 단정하지 않음')
    if job.entry_status != '지원 어려움' and re.search(r'계약직|비정규직|기간제', job.employment) and '인턴' not in job.employment:
        if not re.search(r'정규직.{0,15}전환|전환.{0,15}정규직', job.employment+' '+detail):
            job.entry_status = '확인 필요'
            job.reasons.append('계약직 정규직 전환 가능성 미확인')
    if job.company_type == 'small':
        job.entry_status = '지원 어려움'
        job.reasons.append('대상 기업 규모 미충족')
    elif job.company_type == 'unknown':
        job.entry_status = '확인 필요'
        job.reasons.append('중견급 이상 규모 확인 필요')
    duty_direct_hits = {word.casefold() for word in cfg['mechanical_direct'] if word.casefold() in job.duties.casefold()}
    duty_broad_hits = {word.casefold() for word in cfg['mechanical_broad'] if word.casefold() in job.duties.casefold()}
    direct_mechanical = contains(headline_evidence, cfg['mechanical_direct']) or len(duty_direct_hits) >= 2
    broad_mechanical = contains(headline_evidence, cfg['mechanical_broad']) or len(duty_broad_hits) >= 2
    job.mechanical_status = '관련 있음' if direct_mechanical else '확인 필요' if broad_mechanical or not job.detail_complete else '관련 없음'
    if job.mechanical_status == '확인 필요':
        job.reasons.append('담당업무·전공의 기계공학 관련성 확인 필요')
    for category, words in cfg['categories'].items():
        if contains(evidence, words):
            job.category = category
            break
    job.score = min(100, (35 if contains(job.majors, ['기계', '메카트로닉스']) else 0)
                    + (30 if job.mechanical_status == '관련 있음' else 0)
                    + (20 if job.entry_status == '지원 가능' else 0)
                    + (15 if contains(job.preferences+' '+job.preferred_certificates, cfg['profile_certificates']) else 0))
    job.fit = '매우 높음' if job.score >= 80 else '높음' if job.score >= 55 else '보통' if job.score >= 30 else '낮음'
    if job.entry_status == '지원 어려움':
        job.score, job.fit = 0, '낮음'
    return job
