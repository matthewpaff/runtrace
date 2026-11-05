KINDS={'note','consent','tool_call','tool_result','outcome','error'}

def validate(trace):
    if not isinstance(trace,dict): raise ValueError('Trace must be an object')
    if set(trace)-{'name','scenario','synthetic','budget','events','expected'}: raise ValueError('Unknown trace fields')
    if not isinstance(trace.get('name'),str) or not 1<=len(trace['name'])<=120: raise ValueError('Name must be 1–120 characters')
    if trace.get('synthetic') is not True: raise ValueError('This workbench accepts explicitly synthetic traces only')
    if not isinstance(trace.get('scenario'),str) or len(trace['scenario'])>100: raise ValueError('Invalid scenario')
    budget=trace.get('budget')
    if not isinstance(budget,dict) or set(budget)!={'steps','cost'}: raise ValueError('Budget requires steps and cost')
    if type(budget['steps']) is not int or not 1<=budget['steps']<=1000: raise ValueError('Invalid step budget')
    if type(budget['cost']) not in (int,float) or not 0<=budget['cost']<=100: raise ValueError('Invalid declared cost budget')
    events=trace.get('events')
    if not isinstance(events,list) or not 1<=len(events)<=1000: raise ValueError('Expected 1–1000 events')
    pending=set(); finished=set()
    for i,e in enumerate(events):
        if not isinstance(e,dict) or set(e)-{'seq','kind','text','call_id','tool','request_id','side_effect','cost','evidence','success','effect_id'}: raise ValueError('Invalid event fields')
        if e.get('seq')!=i+1 or type(e.get('seq')) is not int: raise ValueError('Event sequence must be contiguous and ordered')
        if e.get('kind') not in KINDS or not isinstance(e.get('text'),str) or len(e['text'])>8000: raise ValueError('Invalid event kind or text')
        for field in ('call_id','tool','request_id','evidence','effect_id'):
            if field in e and (not isinstance(e[field],str) or len(e[field])>500): raise ValueError('Invalid '+field)
        for field in ('side_effect','success'):
            if field in e and type(e[field]) is not bool: raise ValueError('Invalid '+field)
        if type(e.get('cost',0)) not in (int,float) or not 0<=e.get('cost',0)<=100: raise ValueError('Invalid declared event cost')
        if e['kind']=='tool_call':
            cid=e.get('call_id')
            if not cid or cid in pending or cid in finished or not e.get('tool'): raise ValueError('Tool calls require unique call_id and tool')
            pending.add(cid)
        if e['kind']=='tool_result':
            cid=e.get('call_id')
            if cid not in pending: raise ValueError('Result must follow an unmatched call')
            pending.remove(cid); finished.add(cid)
    if pending: raise ValueError('Every tool call needs a recorded result')
    if not isinstance(trace.get('expected'),list) or any(not isinstance(x,str) or not x or len(x)>200 for x in trace['expected']) or len(trace['expected'])>30: raise ValueError('Invalid expected evidence list')
    return trace
