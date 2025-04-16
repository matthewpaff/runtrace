import unittest,tempfile
from pathlib import Path
from store import Store
from server import simulate

class WorkflowTests(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.store=Store(Path(self.temp.name)/'runs.db')
    def tearDown(self):self.temp.cleanup()
    def test_suite_history_is_immutable_and_baseline_scoped(self):
        dataset={'name':'Release','cases':[{'name':'baseline','trace':simulate('baseline'),'expected_checks':{'Expected evidence':True}}]}
        saved=self.store.save_suite(dataset);first=self.store.execute_suite(saved['id'])
        dataset['cases'][0]['trace']=simulate('timeout');self.store.save_suite(dataset,saved['id']);second=self.store.execute_suite(saved['id'],first['id'])
        self.assertEqual(second['result']['case_regressions'],['baseline']);self.assertEqual(self.store.suite_execution(first['id'])['result']['status'],'pass')
        other=self.store.save_suite(dataset)
        with self.assertRaises(ValueError):self.store.execute_suite(other['id'],first['id'])
    def test_annotations_fork_and_cascade(self):
        r=self.store.save(simulate('baseline'));self.store.annotate(r['id'],2,'Inspect',True)
        with self.assertRaises(ValueError):self.store.annotate(r['id'],0)
        fork=self.store.fork(r['id'],'Tight budget',{'steps':1,'cost':0})
        self.assertEqual(fork['metadata']['origin_id'],r['id']);self.assertEqual(self.store.get(r['id'])['summary']['status'],'pass');self.assertEqual(fork['summary']['status'],'review')
        self.store.delete(r['id']);self.assertEqual(self.store.annotations(r['id']),[])
    def test_batch_invalid_and_duplicate_are_atomic(self):
        t=simulate('baseline')
        with self.assertRaises(ValueError):self.store.import_batch([t,{'name':'bad'}])
        with self.assertRaises(ValueError):self.store.import_batch([t,t])
        self.assertEqual(self.store.list(),[])
        rows=self.store.import_batch([t,simulate('timeout')]);self.assertEqual(len(rows),2);self.assertNotEqual(self.store.fingerprint(rows[0]['id']),self.store.fingerprint(rows[1]['id']))
    def test_lossless_archive_roundtrip(self):
        original=self.store.save(simulate('baseline'));rid=original['id'];self.store.update(rid,{'tags':['test'],'notes':'hello','starred':True});self.store.checkpoint(rid,4);self.store.annotate(rid,2,'bookmark',True)
        archive=self.store.export_recording(rid);copied=self.store.import_recording(archive)
        self.assertEqual(self.store.export_recording(copied['id']),archive)
        archive['cursor']=999
        before=len(self.store.list())
        with self.assertRaises(ValueError):self.store.import_recording(archive)
        self.assertEqual(len(self.store.list()),before)
