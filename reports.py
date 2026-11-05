"""Stable report exports and opt-in recursive literal redaction."""
import csv,io,json,re
from copy import deepcopy
from evaluation import evaluate

SENSITIVE_KEYS={'authorization','password','secret','api_key','token'}

def redact(value,secrets=()):
    if not isinstance(secrets,(list,tuple)) or len(secrets)>100 or any(not isinstance(s,str) or not s or len(s)>1000 for s in secrets):raise ValueError('Redactions must be 1–1000 character literal strings')
    def walk(v):
        if isinstance(v,dict):return {k:('[REDACTED]' if k.casefold() in SENSITIVE_KEYS else walk(x)) for k,x in v.items()}
        if isinstance(v,list):return [walk(x) for x in v]
        if isinstance(v,str):
            for secret in sorted(secrets,key=len,reverse=True):v=v.replace(secret,'[REDACTED]')
            v=re.sub(r'(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+',r'\1[REDACTED]',v)
            return v
        return v
    return walk(value)

def report(trace,secrets=()):
    return redact({'report_version':1,'trace_name':trace['name'],'synthetic':True,'metric_basis':'recorded assertions and declared costs','summary':evaluate(trace)},secrets)

def report_json(trace,secrets=()):return json.dumps(report(trace,secrets),sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False)+'\n'

def safe_cell(value):
    text=str(value)
    return "'"+text if text.lstrip().startswith(('=','+','-','@')) or text.startswith(('\t','\r','\n')) else text

def report_csv(trace,secrets=()):
    data=report(trace,secrets);out=io.StringIO(newline='');writer=csv.writer(out)
    writer.writerow(['trace_name','check','passed','reason','event_sequences'])
    for check in data['summary']['checks']:writer.writerow([safe_cell(data['trace_name']),safe_cell(check['name']),str(check['pass']).lower(),safe_cell(check['detail']),';'.join(map(str,check['event_sequences']))])
    return out.getvalue()

def compare(left,right):
    a=evaluate(left);b=evaluate(right);old={c['name']:c for c in a['checks']}
    changes=[{'name':c['name'],'before':old.get(c['name'],{}).get('pass'),'after':c['pass']} for c in b['checks'] if old.get(c['name'],{}).get('pass')!=c['pass']]
    return {'baseline':left['name'],'candidate':right['name'],'regressions':[c['name'] for c in changes if c['before'] is True and c['after'] is False],'improvements':[c['name'] for c in changes if c['before'] is False and c['after'] is True],'changes':changes,'step_delta':b['steps']-a['steps'],'cost_delta':str(__import__('decimal').Decimal(b['cost_decimal'])-__import__('decimal').Decimal(a['cost_decimal']))}
