from pathlib import Path
import json, sqlite3, uuid, datetime
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parent
MAX_IMPORT=262144
KINDS={'note','consent','tool_call','tool_result','outcome','error'}

def validate(trace):
    if not isinstance(trace,dict): raise ValueError('Trace must be an object')
    if set(trace)-{'name','scenario','synthetic','budget','events','expected'}: raise ValueError('Unknown trace fields')
    if not isinstance(trace.get('name'),str) or not 1<=len(trace['name'])<=120: raise ValueError('Name must be 1–120 characters')
    if trace.get('synthetic') is not True: raise ValueError('This workbench accepts explicitly synthetic traces only')
    if not isinstance(trace.get('scenario'),str) or len(trace['scenario'])>100: raise ValueError('Invalid scenario')
    budget=trace.get('budget')
    if not isinstance(budget,dict) or set(budget)!={'steps','cost'}: raise ValueError('Budget requires steps and cost')
    if type(budget['steps']) is not int or not 1<=budget['steps']<=1000: raise ValueError('Invalid step budget')
    if type(budget['cost']) not in (int,float) or not 0<=budget['cost']<=100: raise ValueError('Invalid declared cost budget')
    events=trace.get('events')
    if not isinstance(events,list) or not 1<=len(events)<=1000: raise ValueError('Expected 1–1000 events')
    pending=set(); finished=set()
    for i,e in enumerate(events):
        if not isinstance(e,dict) or set(e)-{'seq','kind','text','call_id','tool','request_id','side_effect','cost','evidence','success','effect_id'}: raise ValueError('Invalid event fields')
        if e.get('seq')!=i+1 or type(e.get('seq')) is not int: raise ValueError('Event sequence must be contiguous and ordered')
        if e.get('kind') not in KINDS or not isinstance(e.get('text'),str) or len(e['text'])>8000: raise ValueError('Invalid event kind or text')
        for field in ('call_id','tool','request_id','evidence','effect_id'):
            if field in e and (not isinstance(e[field],str) or len(e[field])>500): raise ValueError('Invalid '+field)
        for field in ('side_effect','success'):
            if field in e and type(e[field]) is not bool: raise ValueError('Invalid '+field)
        if type(e.get('cost',0)) not in (int,float) or not 0<=e.get('cost',0)<=100: raise ValueError('Invalid declared event cost')
        if e['kind']=='tool_call':
            cid=e.get('call_id')
            if not cid or cid in pending or cid in finished or not e.get('tool'): raise ValueError('Tool calls require unique call_id and tool')
            pending.add(cid)
        if e['kind']=='tool_result':
            cid=e.get('call_id')
            if cid not in pending: raise ValueError('Result must follow an unmatched call')
            pending.remove(cid); finished.add(cid)
    if pending: raise ValueError('Every tool call needs a recorded result')
    if not isinstance(trace.get('expected'),list) or any(not isinstance(x,str) or not x or len(x)>200 for x in trace['expected']) or len(trace['expected'])>30: raise ValueError('Invalid expected evidence list')
    return trace

def evaluate(t):
    events=t['events']; checks=[]; consented=set(); effects={}; duplicate=[]; unconsented=[]; unverifiable=[]
    successful={e['call_id']:e for e in events if e['kind']=='tool_result' and e.get('success') is True}
    for e in events:
        if e['kind']=='consent' and e.get('request_id'): consented.add(e['request_id'])
        if e['kind']=='tool_call' and e.get('side_effect'):
            if e.get('request_id') not in consented: unconsented.append(e['seq'])
            key=e.get('request_id')
            if e['call_id'] in successful:
                effect=successful[e['call_id']].get('effect_id')
                if not key or not effect: unverifiable.append(e['seq'])
                else:
                    prior=effects.setdefault(key,set())
                    if prior and effect not in prior: duplicate.append(e['seq'])
                    prior.add(effect)
    evidence={e.get('evidence') for e in events if e['kind']=='outcome' and e.get('success') is True}
    missing=[x for x in t['expected'] if x not in evidence]
    steps=sum(e['kind']=='tool_call' for e in events); cost=round(sum(e.get('cost',0) for e in events),6)
    for label,ok,detail in [('Expected evidence',not missing,'Missing: '+', '.join(missing) if missing else 'All expected evidence recorded'),('Consent before action',not unconsented,'Unconsented side effects at '+str(unconsented) if unconsented else 'Every side effect follows request-scoped recorded consent'),('Duplicate side effects',not duplicate,'Distinct confirmed effects for repeated request IDs at '+str(duplicate) if duplicate else 'No distinct confirmed effects for repeated request IDs'),('Verifiable effects',not unverifiable,'Missing request or effect IDs at '+str(unverifiable) if unverifiable else 'Successful side-effect receipts identify effects'),('Step budget',steps<=t['budget']['steps'],f"{steps} / {t['budget']['steps']} tool calls"),('Declared cost budget',cost<=t['budget']['cost'],f"${cost:.3f} / ${t['budget']['cost']:.3f}")]:
        checks.append({'name':label,'pass':ok,'detail':detail})
    return {'checks':checks,'passed':sum(c['pass'] for c in checks),'total':len(checks),'steps':steps,'cost':cost,'events':len(events),'status':'pass' if all(c['pass'] for c in checks) else 'review'}

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

def simulate(scenario,steps=4,cost=.08):
    if scenario not in ('baseline','timeout','rate_limit','duplicate'): raise ValueError('Unknown scenario')
    t={'name':{'baseline':'Release notes · clean handoff','timeout':'Release notes · tool timeout','rate_limit':'Release notes · rate limit','duplicate':'Release notes · duplicate delivery'}[scenario],'scenario':scenario,'synthetic':True,'budget':{'steps':steps,'cost':cost},'expected':['sources_verified','delivery_confirmed'],'events':[]}
    def emit(kind,text,**kw): t['events'].append(dict(seq=len(t['events'])+1,kind=kind,text=text,**kw))
    emit('note','Inspect release sources before preparing the handoff.')
    emit('tool_call','Read the synthetic release manifest.',call_id='read-1',tool='manifest.read',cost=.012)
    failed=scenario in ('timeout','rate_limit')
    emit('tool_result',{'timeout':'Simulated timeout after 2 seconds. No external tool ran.','rate_limit':'Simulated HTTP 429. Retry-after recorded; no automatic retry.'}.get(scenario,'Three release entries verified against the fixture.'),call_id='read-1',success=not failed)
    if failed:
        emit('error','Stopped safely: source verification unavailable. Delivery withheld.')
    else:
        emit('outcome','Source manifest verified.',evidence='sources_verified',success=True)
        if scenario!='duplicate': emit('consent','Recorded synthetic operator consent for this request.',request_id='release-42')
        emit('tool_call','Simulate delivery of release summary.',call_id='send-1',tool='notification.send',request_id='release-42',side_effect=True,cost=.024)
        emit('tool_result','Synthetic delivery accepted.',call_id='send-1',success=True,effect_id='delivery-1')
        if scenario=='duplicate':
            emit('note','Fault injection: retry without deduplication or consent.')
            emit('tool_call','Simulate duplicate delivery.',call_id='send-2',tool='notification.send',request_id='release-42',side_effect=True,cost=.024)
            emit('tool_result','Second synthetic delivery accepted.',call_id='send-2',success=True,effect_id='delivery-2')
        emit('outcome','Delivery receipt recorded.',evidence='delivery_confirmed',success=True)
    return validate(t)

def serve(port=8763, db_path=None):
    store=Store(db_path or ROOT/'runtrace.sqlite3')
    if not store.list():
        for scenario in ('baseline','timeout','duplicate'): store.save(simulate(scenario))
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def send(self,status,payload):
            body=json.dumps(payload,allow_nan=False).encode(); self.send_response(status); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
        def do_GET(self):
            path=urlsplit(self.path).path
            if path=='/api/health': return self.send(200,{'status':'ok','mode':'synthetic-recorded'})
            if path=='/api/runs': return self.send(200,store.list())
            if path.startswith('/api/runs/'):
                item=store.get(path.rsplit('/',1)[-1]); return self.send(200,item) if item else self.send(404,{'error':'Run not found'})
            assets={'/':'index.html','/app.js':'app.js','/style.css':'style.css'}
            if path not in assets: return self.send(404,{'error':'Not found'})
            f=ROOT/'static'/assets[path]; body=f.read_bytes(); self.send_response(200); self.send_header('Content-Type',{'html':'text/html; charset=utf-8','css':'text/css','js':'text/javascript'}[f.suffix[1:]]); self.send_header('Content-Length',str(len(body))); self.send_header('X-Content-Type-Options','nosniff'); self.end_headers(); self.wfile.write(body)
        def do_POST(self):
            try:
                if self.headers.get('Origin') and self.headers['Origin'] != 'http://'+self.headers.get('Host',''): return self.send(403,{'error':'Cross-origin writes denied'})
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=MAX_IMPORT: raise ValueError('JSON payload must be 1–262144 bytes')
                data=json.loads(self.rfile.read(length),parse_constant=lambda x: (_ for _ in ()).throw(ValueError('Nonfinite numbers rejected')))
                path=urlsplit(self.path).path
                if path=='/api/import': result=store.save(data)
                elif path=='/api/simulate':
                    if not isinstance(data,dict): raise ValueError('Request must be an object')
                    result=store.save(simulate(data.get('scenario'),data.get('steps',4),data.get('cost',.08)))
                else: return self.send(404,{'error':'Not found'})
                self.send(201,result)
            except (ValueError,TypeError,KeyError,UnicodeDecodeError) as e: self.send(400,{'error':str(e)})
    print(f'Runtrace listening at http://127.0.0.1:{port}')
    ThreadingHTTPServer(('127.0.0.1',port),Handler).serve_forever()

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(); p.add_argument('--port',type=int,default=8763); p.add_argument('--db'); args=p.parse_args(); serve(args.port,args.db)
