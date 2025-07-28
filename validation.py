"""Versioned, inert trace data contract. No execution is supported."""
from decimal import Decimal, InvalidOperation
from copy import deepcopy

KINDS={'note','consent','tool_call','tool_result','outcome','error','cancelled'}
VERSION=2

def amount(value, label='cost', maximum=100):
    if type(value) not in (int,float,str): raise ValueError('Invalid '+label)
    try: result=Decimal(str(value))
    except InvalidOperation: raise ValueError('Invalid '+label)
    if not result.is_finite() or not 0<=result<=maximum: raise ValueError('Invalid '+label)
    return result

def migrate(trace):
    """Copy legacy version-one traces into the current explicit schema."""
    if not isinstance(trace,dict): raise ValueError('Trace must be an object')
    version=trace.get('schema_version',1)
    if type(version) is not int or version not in (1,2): raise ValueError('Unsupported schema version')
    result=deepcopy(trace)
    result['schema_version']=VERSION
    return result

def validate(trace):
    if not isinstance(trace,dict): raise ValueError('Trace must be an object')
    if set(trace)-{'schema_version','name','scenario','synthetic','budget','events','expected','policy'}: raise ValueError('Unknown trace fields')
    migrate(trace)
    if not isinstance(trace.get('name'),str) or not 1<=len(trace['name'])<=120: raise ValueError('Name must be 1–120 characters')
    if trace.get('synthetic') is not True: raise ValueError('Only explicitly synthetic traces are accepted')
    if not isinstance(trace.get('scenario'),str) or len(trace['scenario'])>100: raise ValueError('Invalid scenario')
    budget=trace.get('budget')
    if not isinstance(budget,dict) or set(budget)!={'steps','cost'}: raise ValueError('Budget requires steps and cost')
    if type(budget['steps']) is not int or not 1<=budget['steps']<=1000: raise ValueError('Invalid step budget')
    amount(budget['cost'],'declared cost budget')
    policy=trace.get('policy',{})
    if not isinstance(policy,dict) or set(policy)-{'consent','tools'}: raise ValueError('Invalid policy')
    if policy.get('consent','request') not in ('request','single_use'): raise ValueError('Invalid consent policy')
    if 'tools' in policy and (not isinstance(policy['tools'],list) or len(policy['tools'])>100 or any(not isinstance(x,str) or not x or len(x)>500 for x in policy['tools'])): raise ValueError('Invalid tool allowlist')
    events=trace.get('events')
    if not isinstance(events,list) or not 1<=len(events)<=1000: raise ValueError('Expected 1–1000 events')
    pending={}; finished=set(); cancelled=False
    for i,e in enumerate(events):
        if not isinstance(e,dict) or set(e)-{'seq','kind','text','call_id','tool','request_id','side_effect','cost','evidence','success','effect_id','at_ms','usage','status'}: raise ValueError('Invalid event fields')
        if e.get('seq')!=i+1 or type(e.get('seq')) is not int: raise ValueError('Event sequence must be contiguous and ordered')
        if not isinstance(e.get('kind'),str) or e['kind'] not in KINDS or not isinstance(e.get('text'),str) or len(e['text'])>8000: raise ValueError('Invalid event kind or text')
        for field in ('call_id','tool','request_id','evidence','effect_id'):
            if field in e and (not isinstance(e[field],str) or not e[field] or len(e[field])>500): raise ValueError('Invalid '+field)
        for field in ('side_effect','success'):
            if field in e and type(e[field]) is not bool: raise ValueError('Invalid '+field)
        if 'success' in e and e['kind'] not in ('tool_result','outcome'):raise ValueError('Success belongs only to results and outcomes')
        if 'effect_id' in e and e['kind']!='tool_result':raise ValueError('Effect IDs belong only to tool results')
        amount(e.get('cost',0),'declared event cost')
        if 'at_ms' in e:
            if type(e['at_ms']) is not int or not 0<=e['at_ms']<=86400000: raise ValueError('Invalid recorded time')
            if any(x.get('at_ms',0)>e['at_ms'] for x in events[:i]): raise ValueError('Recorded times must be monotonic')
        if 'usage' in e:
            u=e['usage']
            if not isinstance(u,dict) or set(u)!={'input_tokens','output_tokens'} or any(type(n) is not int or not 0<=n<=10000000 for n in u.values()): raise ValueError('Invalid recorded provider usage')
        if 'status' in e and e['status'] not in ('success','error','cancelled','unknown'): raise ValueError('Invalid result status')
        if 'status' in e and e['kind'] not in ('tool_result','outcome'):raise ValueError('Status belongs only to results and outcomes')
        if 'status' in e and 'success' in e and (e['status']=='success')!=e['success']:raise ValueError('Conflicting result status and success')
        if e['kind']=='cancelled':
            if pending:raise ValueError('Resolve pending calls with cancelled results before cancelling the run')
            cancelled=True
        elif cancelled and e['kind'] in ('outcome','consent'):
            raise ValueError('Cancelled runs cannot record later consent or outcomes')
        if e['kind']=='tool_call':
            if cancelled:raise ValueError('Tool call after run cancellation')
            cid=e.get('call_id')
            if not cid or cid in pending or cid in finished or not e.get('tool'): raise ValueError('Tool calls require unique call_id and tool')
            pending[cid]=e
        if e['kind']=='tool_result':
            cid=e.get('call_id')
            if cid not in pending: raise ValueError('Result must follow an unmatched call')
            if 'status' in e and 'success' in e and (e['status']=='success')!=e['success']: raise ValueError('Conflicting result status and success')
            del pending[cid]; finished.add(cid)
    if pending: raise ValueError('Every tool call needs a recorded result')
    if not isinstance(trace.get('expected'),list) or len(trace['expected'])>30 or any(not isinstance(x,str) or not x or len(x)>200 for x in trace['expected']): raise ValueError('Invalid expected evidence list')
    if len(set(trace['expected']))!=len(trace['expected']): raise ValueError('Duplicate expected evidence')
    return trace
