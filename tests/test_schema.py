import unittest
from server import simulate
from validation import validate,migrate

class SchemaTests(unittest.TestCase):
    def test_version_migration_is_non_mutating(self):
        t=simulate('baseline'); old=dict(t); new=migrate(t)
        self.assertEqual(t,old);self.assertEqual(new['schema_version'],2)
        for version in (True,0,3,'2'):
            t['schema_version']=version
            with self.assertRaises(ValueError):validate(t)
    def test_recorded_time_and_usage_validation(self):
        t=simulate('baseline');t['events'][0]['at_ms']=50;t['events'][1]['at_ms']=49
        with self.assertRaises(ValueError):validate(t)
        del t['events'][1]['at_ms'];t['events'][0]['usage']={'input_tokens':True,'output_tokens':1}
        with self.assertRaises(ValueError):validate(t)
    def test_invalid_policy_and_event_discriminants(self):
        for policy in ({'consent':'global'},{'tools':['']},{'extra':True}):
            t=simulate('baseline');t['policy']=policy
            with self.assertRaises(ValueError):validate(t)
        t=simulate('baseline');t['events'][0]['kind']=[]
        with self.assertRaises(ValueError):validate(t)
    def test_conflicting_result_status(self):
        t=simulate('baseline');t['events'][2]['status']='error'
        with self.assertRaises(ValueError):validate(t)
