import unittest,tempfile,sqlite3,json
from pathlib import Path
from store import Store
from server import simulate

class StoreTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'runs.db';self.store=Store(self.path)
    def tearDown(self):self.tmp.cleanup()
    def test_old_database_migrates_without_losing_trace(self):
        p=Path(self.tmp.name)/'old.db'
        with sqlite3.connect(p) as db:
            db.execute('CREATE TABLE runs(id TEXT PRIMARY KEY,created TEXT NOT NULL,trace TEXT NOT NULL)');db.execute('INSERT INTO runs VALUES(?,?,?)',('legacy','2026',json.dumps(simulate('baseline'))))
        migrated=Store(p).get('legacy');self.assertEqual(migrated['metadata']['tags'],[]);self.assertEqual(migrated['cursor'],0)
    def test_metadata_archive_filter_delete(self):
        r=self.store.save(simulate('baseline'));rid=r['id']
        self.store.update(rid,{'tags':['release','release'],'notes':'review later','starred':True})
        self.assertEqual(self.store.search('later',tag='release',starred=True)['total'],1)
        self.store.update(rid,{'archived':True});self.assertEqual(self.store.search()['total'],0)
        self.assertEqual(self.store.search(archived=True)['total'],1);self.assertTrue(self.store.delete(rid));self.assertIsNone(self.store.get(rid));self.assertFalse(self.store.delete(rid))
    def test_checkpoint_persists_and_cannot_reexecute(self):
        r=self.store.save(simulate('baseline'));self.store.checkpoint(r['id'],3)
        self.assertEqual(Store(self.path).get(r['id'])['cursor'],3)
        for n in (-1,1001,True):
            with self.assertRaises(ValueError):self.store.checkpoint(r['id'],n)
    def test_invalid_metadata_does_not_mutate_run(self):
        r=self.store.save(simulate('baseline'))
        for changes in ({'starred':1},{'tags':['']},{'notes':[]},{'trace':{}}):
            with self.assertRaises(ValueError):self.store.update(r['id'],changes)
        self.assertEqual(self.store.get(r['id'])['metadata'],r['metadata'])
    def test_pagination_is_stable_and_validated(self):
        for i in range(3):self.store.save(simulate('baseline'))
        a=self.store.search(limit=2);b=self.store.search(offset=2,limit=2)
        self.assertEqual(a['total'],3);self.assertFalse({r['id'] for r in a['items']}&{r['id'] for r in b['items']})
        with self.assertRaises(ValueError):self.store.search(limit=0)
