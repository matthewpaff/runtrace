import unittest,copy
from server import simulate
from reports import trace_diff

class DiffTests(unittest.TestCase):
    def test_annotation_position_shift_does_not_misalign_calls(self):
        a=simulate('baseline');b=copy.deepcopy(a);b['events'].insert(1,{'seq':2,'kind':'note','text':'Additional annotation'})
        for i,e in enumerate(b['events']):e['seq']=i+1
        diff=trace_diff(a,b);self.assertEqual(len(diff),2);self.assertTrue(all(c['change']=='unchanged' for c in diff))
    def test_retries_align_by_occurrence_and_distinct_receipts(self):
        a=simulate('baseline');b=simulate('duplicate');diff=trace_diff(a,b)
        self.assertEqual([c['change'] for c in diff],['unchanged','unchanged','added'])
        b['events'][5]['effect_id']='changed-receipt'
        self.assertEqual(trace_diff(a,b)[1]['change'],'changed')
