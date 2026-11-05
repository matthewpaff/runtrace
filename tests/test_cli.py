import json,subprocess,sys,tempfile,unittest
from pathlib import Path
from server import simulate

ROOT=Path(__file__).resolve().parents[1]
class CLITests(unittest.TestCase):
    def run_cli(self,args,stdin=None):return subprocess.run([sys.executable,str(ROOT/'cli.py'),*args],input=stdin,text=True,capture_output=True,cwd=ROOT)
    def test_evaluate_stdin_pass_and_review_exit_codes(self):
        good=self.run_cli(['evaluate','-'],json.dumps(simulate('baseline')));self.assertEqual(good.returncode,0);self.assertTrue(json.loads(good.stdout)['synthetic'])
        bad=self.run_cli(['evaluate','-'],json.dumps(simulate('timeout')));self.assertEqual(bad.returncode,1)
    def test_errors_are_json_and_do_not_emit_report(self):
        for raw in ('null','{"x":1,"x":2}','x'*262145):
            p=self.run_cli(['evaluate','-'],raw);self.assertEqual(p.returncode,2);self.assertEqual(p.stdout,'');self.assertIn('error',json.loads(p.stderr))
        p=self.run_cli(['evaluate','missing-trace-file.json']);self.assertEqual(p.returncode,2)
    def test_batch_import_persists_only_valid_data(self):
        with tempfile.TemporaryDirectory() as temp:
            db=str(Path(temp)/'runs.db');result=self.run_cli(['batch-import','-','--db',db],json.dumps([simulate('baseline'),simulate('timeout')]))
            self.assertEqual(result.returncode,0);self.assertEqual(len(json.loads(result.stdout)['ids']),2)
    def test_compare_stdin_ambiguity_has_clear_error(self):
        p=self.run_cli(['compare','-','-'],'{}');self.assertEqual(p.returncode,2);self.assertIn('Only one',p.stderr)
    def test_list_reads_existing_runs_without_creating_a_database(self):
        with tempfile.TemporaryDirectory() as temp:
            db=Path(temp)/'runs.db'
            absent=self.run_cli(['list','--db',str(db)])
            self.assertEqual(absent.returncode,2);self.assertFalse(db.exists())
            self.assertEqual(self.run_cli(['import','-','--db',str(db)],json.dumps(simulate('baseline'))).returncode,0)
            listed=self.run_cli(['list','--db',str(db)])
            self.assertEqual(listed.returncode,0)
            self.assertEqual(json.loads(listed.stdout)[0]['name'],simulate('baseline')['name'])
