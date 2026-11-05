import unittest, tempfile, copy, json
from pathlib import Path
from server import validate, evaluate, simulate, Store

class TraceTests(unittest.TestCase):
    def test_order_and_state(self):
        t=simulate('baseline'); t['events'][1]['seq']=9
        with self.assertRaises(ValueError): validate(t)
        t=simulate('baseline'); t['events'][2]['call_id']='never-called'
        with self.assertRaises(ValueError): validate(t)
        t=simulate('baseline'); t['events'].pop(2)
        for i,e in enumerate(t['events']): e['seq']=i+1
        with self.assertRaises(ValueError): validate(t)
    def test_budget_failure(self):
        result=evaluate(simulate('baseline',1,.001))
        self.assertFalse(result['checks'][4]['pass']);self.assertFalse(result['checks'][5]['pass'])
    def test_expected_and_consent(self):
        self.assertEqual(evaluate(simulate('baseline'))['status'],'pass')
        self.assertFalse(evaluate(simulate('timeout'))['checks'][0]['pass'])
        result=evaluate(simulate('duplicate'))
        self.assertFalse(result['checks'][1]['pass']);self.assertFalse(result['checks'][2]['pass'])
        t=simulate('baseline');t['events'][4]['request_id']='other-request'
        self.assertFalse(evaluate(t)['checks'][1]['pass'])
    def test_failed_retry_is_not_duplicate_success(self):
        t=simulate('duplicate');t['events'][5]['success']=False
        self.assertTrue(evaluate(t)['checks'][2]['pass'])
    def test_idempotent_retry_and_missing_receipt(self):
        t=simulate('duplicate');t['events'][8]['effect_id']='delivery-1'
        self.assertTrue(evaluate(t)['checks'][2]['pass'])
        del t['events'][8]['effect_id']
        self.assertFalse(evaluate(t)['checks'][3]['pass'])
    def test_persistence_and_stable_summary(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'runs.db';run=Store(path).save(simulate('baseline'))
            loaded=Store(path).get(run['id']);self.assertEqual(run,loaded)
            self.assertEqual(len(Store(path).list()),1);self.assertIsNone(Store(path).get('unknown'))
    def test_import_validation(self):
        for invalid in (None,[],{'name':'x'}):
            with self.assertRaises(ValueError): validate(invalid)
        for field,value in [('synthetic',False),('budget',{'steps':True,'cost':0}),('expected','no')]:
            t=simulate('baseline');t[field]=value
            with self.assertRaises(ValueError):validate(t)
        t=simulate('baseline');t['events'][0]['command']='powershell'
        with self.assertRaises(ValueError):validate(t)
        t=simulate('baseline');t['budget']['cost']=float('nan')
        with self.assertRaises(ValueError):validate(t)
        t=simulate('baseline');t['events'][0]['text']='<script>alert(1)</script>'
        self.assertEqual(validate(json.loads(json.dumps(t))),t)

if __name__=='__main__': unittest.main()
