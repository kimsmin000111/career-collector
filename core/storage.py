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
          CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, started_at TEXT, finished_at TEXT, mode TEXT, status TEXT, record TEXT);
        ''')
        columns={r['name'] for r in self.db.execute('PRAGMA table_info(sources)')}
        for name,definition in (
            ('last_count','INTEGER NOT NULL DEFAULT 0'),('previous_count','INTEGER NOT NULL DEFAULT 0'),
            ('consecutive_failures','INTEGER NOT NULL DEFAULT 0'),('error_kind',"TEXT NOT NULL DEFAULT ''")
        ):
            if name not in columns:self.db.execute(f'ALTER TABLE sources ADD COLUMN {name} {definition}')
        self.db.commit()
    def jobs(self):
        return [Job(**json.loads(r['record'])) for r in self.db.execute('SELECT record FROM jobs ORDER BY id')]
    def upsert(self, job):
        job.official_url = canonical_url(job.official_url)
        job.id = job.id or identity(job)
        existing = self.db.execute('SELECT record FROM jobs WHERE id=?', (job.id,)).fetchone()
        if not existing:
            for old in self.jobs():
                if old.company == job.company and canonical_url(old.official_url) == job.official_url and old.role == job.role:
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
    def source_state(self, source):
        row=self.db.execute('SELECT * FROM sources WHERE id=?',(source,)).fetchone()
        return dict(row) if row else {'last_count':0,'previous_count':0,'consecutive_failures':0,'status':'never'}
    def source_result(self, source, status, error='', count=0, error_kind=''):
        timestamp=now_iso()
        success=timestamp if status=='ok' else None
        old=self.source_state(source)
        previous=old.get('last_count',0) or 0
        last_count=count if status=='ok' else previous
        failures=0 if status=='ok' else (old.get('consecutive_failures',0) or 0)+1
        self.db.execute('''INSERT INTO sources(id,checked_at,success_at,status,error,last_count,previous_count,consecutive_failures,error_kind)
          VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET checked_at=excluded.checked_at,
          success_at=COALESCE(excluded.success_at,sources.success_at),status=excluded.status,error=excluded.error,
          last_count=excluded.last_count,previous_count=excluded.previous_count,
          consecutive_failures=excluded.consecutive_failures,error_kind=excluded.error_kind''',
          (source,timestamp,success,status,error,last_count,previous,failures,error_kind))
        self.db.commit()
        return self.source_state(source)
    def begin_run(self, mode):
        run_id=now_iso()
        self.db.execute('INSERT INTO runs(id,started_at,mode,status,record) VALUES (?,?,?,?,?)',(run_id,run_id,mode,'running','{}'))
        self.db.commit();return run_id
    def finish_run(self, run_id, status, record):
        self.db.execute('UPDATE runs SET finished_at=?,status=?,record=? WHERE id=?',(now_iso(),status,json.dumps(record,ensure_ascii=False),run_id))
        self.db.commit()
    def close(self):
        self.db.close()
