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
    return json.loads(raw.decode('utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Nonfinite JSON number')))
