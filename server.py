from pathlib import Path
import json, sqlite3, uuid, datetime
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parent
MAX_IMPORT=262144
from validation import validate
from evaluation import evaluate
from store import Store

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
