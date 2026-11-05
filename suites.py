"""Data-only suites assert named deterministic checks, not model benchmarks."""
from evaluation import evaluate
from validation import validate


def run_suite(dataset):
    if not isinstance(dataset,dict) or set(dataset)!={'name','cases'} or not isinstance(dataset['name'],str) or not 1<=len(dataset['name'])<=120:raise ValueError('Invalid dataset')
    cases=dataset['cases']
    if not isinstance(cases,list) or not 1<=len(cases)<=100:raise ValueError('Expected 1–100 dataset cases')
    results=[];names=set()
    for case in cases:
        if not isinstance(case,dict) or set(case)!={'name','trace','expected_checks'} or not isinstance(case['name'],str) or not case['name'] or case['name'] in names:raise ValueError('Cases require unique names, trace, and expected_checks')
        names.add(case['name']);validate(case['trace']);summary=evaluate(case['trace']);actual={c['name']:c['pass'] for c in summary['checks']};expected=case['expected_checks']
        if not isinstance(expected,dict) or not expected or any(k not in actual or type(v) is not bool for k,v in expected.items()):raise ValueError('Unknown check name or invalid expectation')
        differences=[{'check':k,'expected':v,'actual':actual[k]} for k,v in sorted(expected.items()) if actual[k]!=v]
        results.append({'name':case['name'],'pass':not differences,'differences':differences,'summary':summary})
    return {'name':dataset['name'],'synthetic':True,'cases':results,'passed':sum(c['pass'] for c in results),'total':len(results),'status':'pass' if all(c['pass'] for c in results) else 'regression'}
