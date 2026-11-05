"""Shared strict UTF-8 JSON envelope parsing for CLI and HTTP."""
import json
MAX_BYTES=262144

def unique_pairs(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError('Duplicate JSON key: '+key)
        result[key]=value
    return result

def parse_json(raw):
    if not isinstance(raw,bytes) or not 0<len(raw)<=MAX_BYTES:raise ValueError('JSON payload must be 1–262144 bytes')
    try:
        value=json.loads(raw.decode('utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Nonfinite JSON number')))
    except (RecursionError,UnicodeDecodeError) as error:raise ValueError('JSON nesting or encoding limit exceeded') from error
    stack=[(value,0)]
    while stack:
        item,depth=stack.pop()
        if depth>32:raise ValueError('JSON nesting exceeds 32 levels')
        if isinstance(item,dict):stack.extend((v,depth+1) for v in item.values())
        elif isinstance(item,list):stack.extend((v,depth+1) for v in item)
    return value

def query_fields(query,allowed):
    from urllib.parse import parse_qs
    values=parse_qs(query,keep_blank_values=True)
    if set(values)-set(allowed) or any(len(v)!=1 for v in values.values()):raise ValueError('Unknown or repeated query field')
    if any(len(v[0])>1000 for v in values.values()):raise ValueError('Query field too long')
    for key in ('starred','archived'):
        if key in values and values[key][0] not in ('true','false'):raise ValueError(key+' must be true or false')
    return values
