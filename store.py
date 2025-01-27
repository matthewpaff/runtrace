import sqlite3, uuid, datetime, json
from contextlib import contextmanager
from validation import validate
from evaluation import evaluate

class Store:
    def __init__(self,path):
        self.path=str(path)
        with self.connect() as db: db.execute('CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, created TEXT NOT NULL, trace TEXT NOT NULL)')
    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path)
        try:
            with db: yield db
        finally: db.close()
    def save(self,t):
        validate(t); rid=uuid.uuid4().hex[:12]
        with self.connect() as db: db.execute('INSERT INTO runs VALUES (?,?,?)',(rid,datetime.datetime.now(datetime.timezone.utc).isoformat(),json.dumps(t,allow_nan=False)))
        return self.get(rid)
    def get(self,rid):
        with self.connect() as db: row=db.execute('SELECT id,created,trace FROM runs WHERE id=?',(rid,)).fetchone()
        if not row: return None
        t=json.loads(row[2]); return {'id':row[0],'created':row[1],'trace':t,'summary':evaluate(t)}
    def list(self):
        with self.connect() as db: ids=[r[0] for r in db.execute('SELECT id FROM runs ORDER BY created DESC,id DESC')]
        return [self.get(rid) for rid in ids]
