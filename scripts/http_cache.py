import sys,json,sqlite3
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core.storage import Storage
store=Storage('data/jobs.db');path=Path('.cache/pages.json')
if sys.argv[1]=='restore' and path.exists():
    for row in json.loads(path.read_text(encoding='utf-8')):
        store.db.execute('INSERT OR REPLACE INTO pages VALUES (?,?,?,?,?)',row)
    store.db.commit()
elif sys.argv[1]=='save':
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps([list(r) for r in store.db.execute('SELECT * FROM pages')],ensure_ascii=False),encoding='utf-8')
store.close()
