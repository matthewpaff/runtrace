from contextlib import contextmanager
import http.client,json,socket,subprocess,sys,tempfile,time,unittest
from pathlib import Path

@contextmanager
def local_server():
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    with tempfile.TemporaryDirectory() as temp:
        process=subprocess.Popen([sys.executable,'server.py','--port',str(port),'--db',str(Path(temp)/'runs.db')],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,cwd=Path(__file__).resolve().parents[1])
        def call(path,body=None,headers=None):
            connection=http.client.HTTPConnection('127.0.0.1',port,timeout=3)
            h={'Content-Type':'application/json',**(headers or {})}
            connection.request('POST' if body is not None else 'GET',path,body=body,headers=h);response=connection.getresponse();status=response.status;data=response.read();connection.close()
            return status,json.loads(data)
        try:
            for _ in range(100):
                try:call('/api/health');break
                except OSError:time.sleep(.03)
            else:raise RuntimeError('Server did not start')
            yield call,port
        finally:process.terminate();process.wait(timeout=5)

class HTTPV2Tests(unittest.TestCase):
    def test_host_media_type_and_duplicate_key_rejected(self):
        with local_server() as (call,port):
            self.assertEqual(call('/api/health',headers={'Host':'attacker.example'})[0],403)
            self.assertEqual(call('/api/simulate','{}',{'Content-Type':'text/plain'})[0],415)
            self.assertEqual(call('/api/simulate','{"scenario":"baseline","scenario":"timeout"}')[0],400)
            self.assertEqual(call('/api/simulate','{"scenario":"baseline","unknown":true}')[0],400)
    def test_metadata_checkpoint_archive_and_not_found(self):
        with local_server() as (call,port):
            status,run=call('/api/simulate','{"scenario":"baseline"}');rid=run['id'];self.assertEqual(status,201)
            self.assertEqual(call('/api/runs/'+rid+'/metadata','{"starred":true}')[1]['metadata']['starred'],True)
            self.assertEqual(call('/api/runs/'+rid+'/checkpoint','{"cursor":999}')[0],400)
            self.assertEqual(call('/api/runs/'+rid+'/checkpoint','{"cursor":3}')[1]['cursor'],3)
            archive=call('/api/runs/'+rid+'/archive')[1];self.assertEqual(call('/api/archive/import',json.dumps(archive))[0],201)
            self.assertEqual(call('/api/runs/000000000000/metadata','{}')[0],404)
            self.assertEqual(call('/api/runs/'+rid+'/delete','{"confirm":true}')[0],201)
            self.assertEqual(call('/api/runs/'+rid)[0],404)

    def test_query_contract_rejects_silent_boolean_and_repeated_fields(self):
        with local_server() as (call,port):
            for query in ('starred=yes','archived=1','q=a&q=b','unknown=x','offset=-1','limit=101'):
                self.assertEqual(call('/api/search?'+query)[0],400,query)
            self.assertEqual(call('/api/search?starred=true&limit=1')[0],200)
    def test_export_rejects_unknown_or_ambiguous_formats(self):
        with local_server() as (call,port):
            rid=call('/api/simulate','{"scenario":"baseline"}')[1]['id']
            for suffix in ('?format=xml','?format=csv&format=json','?unknown=1'):
                self.assertEqual(call('/api/runs/'+rid+'/export'+suffix)[0],400,suffix)
