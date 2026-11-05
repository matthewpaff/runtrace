import unittest
from server import simulate
from evaluation import evaluate

class EvaluationTests(unittest.TestCase):
    def test_decimal_boundary_has_no_float_drift(self):
        t=simulate('baseline');t['budget']['cost']='0.3'
        for e in t['events']:e.pop('cost',None)
        t['events'][1]['cost']='0.1';t['events'][5]['cost']='0.2'
        s=evaluate(t);self.assertEqual(s['cost_decimal'],'0.3');self.assertTrue(s['checks'][5]['pass'])
    def test_single_use_consent_consumed_on_attempt(self):
        t=simulate('duplicate');t['policy']={'consent':'single_use'}
        t['events'][3]['kind']='consent';t['events'][3]['request_id']='release-42'
        t['events'][3].pop('success');t['events'][3].pop('evidence')
        s=evaluate(t);self.assertEqual(s['checks'][1]['event_sequences'],[8])
    def test_tool_scoped_consent_and_allowlist(self):
        t=simulate('baseline');t['events'][4]['tool']='different';t['policy']={'tools':['manifest.read']}
        s=evaluate(t);self.assertFalse(s['checks'][1]['pass']);self.assertFalse(s['checks'][6]['pass'])
    def test_unknown_result_is_not_assumed_failed(self):
        t=simulate('baseline');del t['events'][6]['success']
        s=evaluate(t);self.assertFalse(s['checks'][7]['pass']);self.assertEqual(s['result_counts']['unknown'],1)
    def test_timing_and_usage_are_recorded_not_inferred(self):
        t=simulate('baseline');s=evaluate(t);self.assertFalse(s['usage_recorded']);self.assertEqual(s['recorded_latencies'],[])
        t['events'][1]['at_ms']=10;t['events'][2]['at_ms']=50;t['events'][2]['usage']={'input_tokens':8,'output_tokens':3}
        s=evaluate(t);self.assertEqual(s['recorded_latencies'][0]['duration_ms'],40);self.assertEqual(s['recorded_usage']['input_tokens'],8)
    def test_cancelled_result_has_explicit_outcome(self):
        t=simulate('baseline');t['events'][6].pop('success');t['events'][6]['status']='cancelled'
        self.assertEqual(evaluate(t)['outcome'],'cancelled')

    def test_simulated_outcomes_do_not_invent_recorded_usage(self):
        self.assertEqual(evaluate(simulate('cancelled'))['outcome'],'cancelled')
        uncertain=evaluate(simulate('unknown'))
        self.assertFalse(uncertain['checks'][7]['pass'])
        self.assertFalse(uncertain['usage_recorded'])
        measured=evaluate(simulate('timed'))
        self.assertTrue(measured['usage_recorded'])
        self.assertEqual(measured['recorded_usage']['input_tokens'],140)
        self.assertEqual(measured['recorded_latencies'][0]['duration_ms'],40)
