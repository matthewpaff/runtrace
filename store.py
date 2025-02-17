"""SQLite-backed runs and resumable recorded-view state."""
import sqlite3, uuid, datetime, json
from contextlib import contextmanager
from validation import validate,migrate
from evaluation import evaluate

class Store:
    def __init__(self,path):
        self.path=str(path)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, created TEXT NOT NULL, trace TEXT NOT NULL)')
            columns={r[1] for r in db.execute('PRAGMA table_info(runs)')}
            for name,definition in [('metadata',"TEXT NOT NULL DEFAULT '{}'"),('cursor','INTEGER NOT NULL DEFAULT 0')]:
                if name not in columns:db.execute(f'ALTER TABLE runs ADD COLUMN {name} {definition}')
            db.execute('PRAGMA user_version=2')
    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path)
        try:
            with db: yield db
        finally: db.close()
    def save(self,t):
        validate(t); t=migrate(t); rid=uuid.uuid4().hex[:12]
        with self.connect() as db: db.execute('INSERT INTO runs(id,created,trace) VALUES (?,?,?)',(rid,datetime.datetime.now(datetime.timezone.utc).isoformat(),json.dumps(t,allow_nan=False)))
        return self.get(rid)
    def get(self,rid):
        with self.connect() as db: row=db.execute('SELECT id,created,trace,metadata,cursor FROM runs WHERE id=?',(rid,)).fetchone()
        if not row: return None
        t=json.loads(row[2]);return {'id':row[0],'created':row[1],'trace':t,'summary':evaluate(t),'metadata':{'tags':[],'notes':'','starred':False,'archived':False,**json.loads(row[3])},'cursor':row[4]}
    def list(self):
        with self.connect() as db: ids=[r[0] for r in db.execute('SELECT id FROM runs ORDER BY created DESC,id DESC')]
        return [self.get(rid) for rid in ids]
    def update(self,rid,changes):
        if not isinstance(changes,dict) or set(changes)-{'tags','notes','starred','archived'}:raise ValueError('Invalid metadata fields')
        if 'tags' in changes and (not isinstance(changes['tags'],list) or len(changes['tags'])>20 or any(not isinstance(t,str) or not 1<=len(t)<=40 for t in changes['tags'])):raise ValueError('Invalid tags')
        if 'notes' in changes and (not isinstance(changes['notes'],str) or len(changes['notes'])>8000):raise ValueError('Invalid notes')
        for key in ('starred','archived'):
            if key in changes and type(changes[key]) is not bool:raise ValueError('Invalid '+key)
        with self.connect() as db:
            row=db.execute('SELECT metadata FROM runs WHERE id=?',(rid,)).fetchone()
            if not row:return None
            metadata=json.loads(row[0]);metadata.update(changes)
            if 'tags' in metadata:metadata['tags']=list(dict.fromkeys(metadata['tags']))
            db.execute('UPDATE runs SET metadata=? WHERE id=?',(json.dumps(metadata),rid))
        return self.get(rid)
    def checkpoint(self,rid,cursor):
        run=self.get(rid)
        if not run:return None
        if type(cursor) is not int or not 0<=cursor<=len(run['trace']['events']):raise ValueError('Cursor outside recorded trace')
        with self.connect() as db:db.execute('UPDATE runs SET cursor=? WHERE id=?',(cursor,rid))
        return self.get(rid)
    def delete(self,rid):
        with self.connect() as db:return db.execute('DELETE FROM runs WHERE id=?',(rid,)).rowcount==1
    def search(self,query='',tag='',starred=False,archived=False,offset=0,limit=20):
        if type(offset) is not int or offset<0 or type(limit) is not int or not 1<=limit<=100:raise ValueError('Invalid pagination')
        rows=[r for r in self.list() if r['metadata']['archived']==archived and (not starred or r['metadata']['starred']) and (not tag or tag in r['metadata']['tags']) and query.casefold() in (r['trace']['name']+' '+r['metadata']['notes']+' '+' '.join(r['metadata']['tags'])).casefold()]
        return {'items':rows[offset:offset+limit],'total':len(rows),'offset':offset,'limit':limit}
