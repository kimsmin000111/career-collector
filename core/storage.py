import json
import sqlite3
from pathlib import Path
from datetime import datetime
from .models import Job, now_iso
from .dedupe import identity, period_key, canonical_url

class Storage:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, record TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS sources(id TEXT PRIMARY KEY, checked_at TEXT, success_at TEXT, status TEXT, error TEXT);
          CREATE TABLE IF NOT EXISTS pages(url TEXT PRIMARY KEY, etag TEXT, modified TEXT, body TEXT NOT NULL, checked_at TEXT);
          CREATE TABLE IF NOT EXISTS candidates(name TEXT PRIMARY KEY, record TEXT NOT NULL);
        ''')
    def jobs(self):
        return [Job(**json.loads(r['record'])) for r in self.db.execute('SELECT record FROM jobs ORDER BY id')]
    def upsert(self, job):
        job.official_url = canonical_url(job.official_url)
        job.id = job.id or identity(job)
        existing = self.db.execute('SELECT record FROM jobs WHERE id=?', (job.id,)).fetchone()
        if not existing:
            for old in self.jobs():
                if old.company == job.company and canonical_url(old.official_url) == job.official_url and (old.role == job.role or old.source_id == job.source_id):
                    existing = {'record': json.dumps(old.record())}
                    job.id = old.id
                    break
        old = json.loads(existing['record']) if existing else None
        job.first_seen = old['first_seen'] if old else job.first_seen or now_iso()
        job.last_checked = job.last_checked or now_iso()
        if old:
            # Missing extracted dates must not erase a known deadline.
            job.start = job.start or old['start']
            job.deadline = job.deadline or old['deadline']
        job.active = not job.closed and (not job.deadline or datetime.fromisoformat(job.deadline) > datetime.fromisoformat(now_iso()))
        compare = lambda d: {k:v for k,v in d.items() if k not in ('first_seen','last_checked')}
        change = 'new' if not old else 'changed' if compare(old) != compare(job.record()) else 'unchanged'
        self.db.execute('INSERT INTO jobs VALUES (?,?) ON CONFLICT(id) DO UPDATE SET record=excluded.record', (job.id,json.dumps(job.record(),ensure_ascii=False)))
        self.db.commit()
        return change
    def expire(self):
        count=0
        for job in self.jobs():
            if job.active and job.deadline and datetime.fromisoformat(job.deadline) <= datetime.fromisoformat(now_iso()):
                job.active=False
                self.db.execute('UPDATE jobs SET record=? WHERE id=?',(json.dumps(job.record(),ensure_ascii=False),job.id))
                count+=1
        self.db.commit()
        return count
    def source_result(self, source, status, error=''):
        timestamp=now_iso()
        success=timestamp if status=='ok' else None
        self.db.execute('INSERT INTO sources VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET checked_at=excluded.checked_at, success_at=COALESCE(excluded.success_at,sources.success_at),status=excluded.status,error=excluded.error', (source,timestamp,success,status,error))
        self.db.commit()
    def close(self):
        self.db.close()
