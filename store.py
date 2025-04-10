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
            db.execute('CREATE TABLE IF NOT EXISTS suites(id TEXT PRIMARY KEY,name TEXT NOT NULL,dataset TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS suite_history(id TEXT PRIMARY KEY,suite_id TEXT NOT NULL,created TEXT NOT NULL,result TEXT NOT NULL,baseline_id TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS event_notes(run_id TEXT NOT NULL,seq INTEGER NOT NULL,note TEXT NOT NULL,bookmarked INTEGER NOT NULL,PRIMARY KEY(run_id,seq))')
            db.execute('PRAGMA user_version=4')
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
        with self.connect() as db:
            db.execute('DELETE FROM event_notes WHERE run_id=?',(rid,))
            return db.execute('DELETE FROM runs WHERE id=?',(rid,)).rowcount==1
    def search(self,query='',tag='',starred=False,archived=False,offset=0,limit=20):
        if type(offset) is not int or offset<0 or type(limit) is not int or not 1<=limit<=100:raise ValueError('Invalid pagination')
        rows=[r for r in self.list() if r['metadata']['archived']==archived and (not starred or r['metadata']['starred']) and (not tag or tag in r['metadata']['tags']) and query.casefold() in (r['trace']['name']+' '+r['metadata']['notes']+' '+' '.join(r['metadata']['tags'])).casefold()]
        return {'items':rows[offset:offset+limit],'total':len(rows),'offset':offset,'limit':limit}

    def save_suite(self,dataset,suite_id=None):
        from suites import run_suite
        run_suite(dataset)
        suite_id=suite_id or uuid.uuid4().hex[:12]
        with self.connect() as db:db.execute('INSERT INTO suites VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,dataset=excluded.dataset',(suite_id,dataset['name'],json.dumps(dataset,allow_nan=False)))
        return self.get_suite(suite_id)
    def get_suite(self,suite_id):
        with self.connect() as db:row=db.execute('SELECT id,dataset FROM suites WHERE id=?',(suite_id,)).fetchone()
        return {'id':row[0],'dataset':json.loads(row[1])} if row else None
    def list_suites(self):
        with self.connect() as db:rows=db.execute('SELECT id,name FROM suites ORDER BY name,id').fetchall()
        return [{'id':r[0],'name':r[1]} for r in rows]
    def delete_suite(self,suite_id):
        with self.connect() as db:return db.execute('DELETE FROM suites WHERE id=?',(suite_id,)).rowcount==1
    def execute_suite(self,suite_id,baseline_id=None):
        from suites import run_suite
        suite=self.get_suite(suite_id)
        if not suite:return None
        result=run_suite(suite['dataset'])
        if baseline_id:
            baseline=self.suite_execution(baseline_id)
            if not baseline or baseline['suite_id']!=suite_id:raise ValueError('Baseline must belong to this suite')
            prior={c['name']:c['pass'] for c in baseline['result']['cases']}
            result['case_regressions']=[c['name'] for c in result['cases'] if prior.get(c['name']) is True and not c['pass']]
            result['new_cases']=[c['name'] for c in result['cases'] if c['name'] not in prior]
        eid=uuid.uuid4().hex[:12]
        with self.connect() as db:db.execute('INSERT INTO suite_history VALUES(?,?,?,?,?)',(eid,suite_id,datetime.datetime.now(datetime.timezone.utc).isoformat(),json.dumps(result,allow_nan=False),baseline_id))
        return self.suite_execution(eid)
    def suite_execution(self,eid):
        with self.connect() as db:row=db.execute('SELECT id,suite_id,created,result,baseline_id FROM suite_history WHERE id=?',(eid,)).fetchone()
        return dict(zip(('id','suite_id','created','result','baseline_id'),(row[0],row[1],row[2],json.loads(row[3]),row[4]))) if row else None
    def suite_history(self,suite_id):
        with self.connect() as db:ids=[r[0] for r in db.execute('SELECT id FROM suite_history WHERE suite_id=? ORDER BY created DESC,id DESC',(suite_id,))]
        return [self.suite_execution(eid) for eid in ids]

    def annotate(self,rid,seq,note='',bookmarked=False):
        run=self.get(rid)
        if not run:return None
        if type(seq) is not int or not 1<=seq<=len(run['trace']['events']):raise ValueError('Invalid event sequence')
        if not isinstance(note,str) or len(note)>4000 or type(bookmarked) is not bool:raise ValueError('Invalid annotation')
        with self.connect() as db:db.execute('INSERT INTO event_notes VALUES(?,?,?,?) ON CONFLICT(run_id,seq) DO UPDATE SET note=excluded.note,bookmarked=excluded.bookmarked',(rid,seq,note,int(bookmarked)))
        return self.annotations(rid)
    def annotations(self,rid):
        with self.connect() as db:rows=db.execute('SELECT seq,note,bookmarked FROM event_notes WHERE run_id=? ORDER BY seq',(rid,)).fetchall()
        return [{'seq':r[0],'note':r[1],'bookmarked':bool(r[2])} for r in rows]

    def fork(self,rid,name,budget=None,policy=None):
        source=self.get(rid)
        if not source:return None
        from copy import deepcopy
        trace=deepcopy(source['trace']);trace['name']=name
        if budget is not None:trace['budget']=budget
        if policy is not None:trace['policy']=policy
        result=self.save(trace)
        with self.connect() as db:db.execute('UPDATE runs SET metadata=? WHERE id=?',(json.dumps({'origin_id':rid,'lineage':'inert policy/budget recording fork'}),result['id']))
        return self.get(result['id'])
