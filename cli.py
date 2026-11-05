"""Offline data-only command line tools. No trace content is executable."""
import argparse,json,sys
from pathlib import Path
from validation import validate
from evaluation import evaluate
from store import Store
from reports import report_json,report_csv,compare
from suites import run_suite
from contracts import parse_json

MAX_BYTES=262144

def read_json(path):
    if path=='-':raw=sys.stdin.buffer.read(MAX_BYTES+1)
    else:
        with open(path,'rb') as source:raw=source.read(MAX_BYTES+1)
    if len(raw)>MAX_BYTES:raise ValueError('JSON file exceeds 256 KiB')
    return parse_json(raw)

def existing_store(path):
    if not Path(path).is_file():raise ValueError('Run database does not exist')
    return Store(path)

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    imp=sub.add_parser('import');imp.add_argument('trace');imp.add_argument('--db',default='runtrace.sqlite3')
    ev=sub.add_parser('evaluate');ev.add_argument('trace');ev.add_argument('--format',choices=['json','csv'],default='json');ev.add_argument('--redact',action='append',default=[])
    comp=sub.add_parser('compare');comp.add_argument('baseline');comp.add_argument('candidate')
    batch=sub.add_parser('batch-import');batch.add_argument('traces');batch.add_argument('--db',default='runtrace.sqlite3')
    archive=sub.add_parser('archive-import');archive.add_argument('archive');archive.add_argument('--db',default='runtrace.sqlite3')
    suite=sub.add_parser('suite');suite.add_argument('dataset')
    listing=sub.add_parser('list');listing.add_argument('--db',default='runtrace.sqlite3')
    args=parser.parse_args(argv)
    try:
        if args.command=='list':
            rows=existing_store(args.db).list()
            print(json.dumps([{'id':r['id'],'name':r['trace']['name'],'created':r['created'],'status':r['summary']['status'],'tags':r['metadata']['tags'],'archived':r['metadata']['archived']} for r in rows]))
            return 0
        if args.command=='batch-import':
            result=Store(args.db).import_batch(read_json(args.traces));print(json.dumps({'ids':[r['id'] for r in result]}));return 0
        if args.command=='archive-import':
            result=Store(args.db).import_recording(read_json(args.archive));print(json.dumps({'id':result['id']}));return 0
        if args.command=='compare' and args.baseline=='-' and args.candidate=='-':raise ValueError('Only one comparison input may use stdin')
        if args.command=='import':result=Store(args.db).save(read_json(args.trace));print(json.dumps({'id':result['id'],'status':result['summary']['status']}));return 0
        if args.command=='evaluate':
            t=read_json(args.trace);validate(t);print((report_json if args.format=='json' else report_csv)(t,args.redact),end='');return 0 if evaluate(t)['status']=='pass' else 1
        if args.command=='compare':
            result=compare(read_json(args.baseline),read_json(args.candidate));print(json.dumps(result,indent=2));return 1 if result['regressions'] else 0
        result=run_suite(read_json(args.dataset));print(json.dumps(result,indent=2));return 0 if result['status']=='pass' else 1
    except (ValueError,TypeError,OSError) as error:print(json.dumps({'error':str(error)}),file=sys.stderr);return 2

if __name__=='__main__':raise SystemExit(main())
