import unittest,json,csv,io
from server import simulate
from reports import report_json,report_csv,redact,compare
from suites import run_suite

class ReportTests(unittest.TestCase):
    def test_report_is_stable_and_csv_is_formula_safe(self):
        t=simulate('baseline');t['name']='=HYPERLINK("bad")'
        self.assertEqual(report_json(t),report_json(t))
        rows=list(csv.reader(io.StringIO(report_csv(t))));self.assertTrue(rows[1][0].startswith("'="));self.assertEqual(len(rows)-1,len(json.loads(report_json(t))['summary']['checks']))
    def test_nested_redaction_does_not_change_source(self):
        value={'text':'Bearer abc.def secret-value','nested':[{'password':'private','memo':'secret-value'}]}
        result=redact(value,['secret-value']);self.assertNotIn('secret-value',str(result));self.assertNotIn('abc.def',str(result));self.assertEqual(value['nested'][0]['password'],'private')
        with self.assertRaises(ValueError):redact(value,[''])
    def test_common_credential_fields_are_removed_recursively(self):
        value={'access_token':'abc','nested':[{'refresh_token':'def','client_secret':'ghi','private_key':'pem'}]}
        result=redact(value)
        self.assertNotIn('abc',str(result));self.assertNotIn('def',str(result));self.assertNotIn('ghi',str(result));self.assertNotIn('pem',str(result))
    def test_comparison_reports_regression_and_improvement(self):
        a=simulate('baseline');b=simulate('timeout')
        self.assertIn('Expected evidence',compare(a,b)['regressions']);self.assertIn('Expected evidence',compare(b,a)['improvements'])
    def test_dataset_expected_failures_are_successful_assertions(self):
        suite={'name':'Faults','cases':[{'name':'Timeout','trace':simulate('timeout'),'expected_checks':{'Expected evidence':False,'Consent before action':True}}]}
        self.assertEqual(run_suite(suite)['status'],'pass')
        suite['cases'][0]['expected_checks']['Expected evidence']=True
        result=run_suite(suite);self.assertEqual(result['status'],'regression');self.assertEqual(result['cases'][0]['differences'][0]['check'],'Expected evidence')
    def test_dataset_unknown_checks_and_duplicate_case_rejected(self):
        case={'name':'x','trace':simulate('baseline'),'expected_checks':{'invented':True}}
        with self.assertRaises(ValueError):run_suite({'name':'x','cases':[case]})
        case['expected_checks']={'Step budget':True}
        with self.assertRaises(ValueError):run_suite({'name':'x','cases':[case,case]})
        with self.assertRaises(ValueError):run_suite({'name':'   ','cases':[case]})
        other={**case,'name':' X '}
        with self.assertRaises(ValueError):run_suite({'name':'x','cases':[case,other]})
