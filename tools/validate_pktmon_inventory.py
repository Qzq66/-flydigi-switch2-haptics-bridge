"""Validate raw read-only inventory without contacting PktMon or loading drivers."""
import argparse,collections,hashlib,json,pathlib,re
ROOT=pathlib.Path(__file__).absolute().parents[1]
PRIVATE=ROOT/'handoff/2026-10-22/work/private'
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run-id',required=True);args=parser.parse_args()
    if not re.fullmatch(r'\d{8}-\d{6}',args.run_id):parser.error('Invalid run identifier')
    source=ROOT/'docs'/('PKTMON_INVENTORY_'+args.run_id+'.json')
    out=ROOT/'docs'/('PKTMON_INVENTORY_VALIDATION_'+args.run_id+'.json')
    if out.exists():raise ValueError('Preserve previous evidence')
    record=json.loads(source.read_text(encoding='utf-8-sig'));raw=PRIVATE/('pktmon-inventory-'+args.run_id)
    if not record.get('administrator') or not record.get('readonly') or not record.get('raw_bytes_preserved'):raise ValueError('Expected administrator raw-byte read-only inventory')
    if record['script_sha256']!=digest(ROOT/'tools/collect_pktmon_inventory_v2.ps1'):raise ValueError('Executed V2 source changed')
    if any(record.get(key) for key in ('capture_started','capture_stopped','filters_changed','network_settings_changed','pico_access','motor_commands')):raise ValueError('Inventory scope differs')
    queries=[q for q in record['queries'] if isinstance(q,dict) and 'query' in q]
    ignored=[q for q in record['queries'] if not (isinstance(q,dict) and 'query' in q)]
    if any(q!={} for q in ignored):raise ValueError('Unknown summary artifact')
    expected={'status':'status.txt','filter list':'filters.txt','list --json':'components.json'}
    if len(queries)!=3 or {q['query'] for q in queries}!=set(expected):raise ValueError('Unexpected query set')
    hashes={}
    for query in queries:
        name=expected[query['query']]
        if query['raw_file']!=name or query['stderr_file']!=name+'.stderr' or query['exit_code']!=0:raise ValueError('Unexpected query result')
        for filename,key in ((name,'sha256'),(name+'.stderr','stderr_sha256')):
            path=raw/filename
            if digest(path)!=query[key]:raise ValueError('Raw query evidence changed')
            hashes[filename]=digest(path)
        if (raw/(name+'.stderr')).stat().st_size!=0:raise ValueError('Query stderr must be reviewed')
    status=(raw/'status.txt').read_bytes().decode('utf-8-sig').strip()
    filters=''.join((raw/'filters.txt').read_bytes().decode('utf-8-sig').split())
    capture_idle=status=='数据包监视器没有运行。'
    filters_empty=filters=='数据包筛选器:无'
    groups=json.loads((raw/'components.json').read_bytes().decode('utf-8-sig'))
    if not isinstance(groups,list) or not all(isinstance(g.get('Components'),list) for g in groups):raise ValueError('Unexpected component inventory schema')
    components=[c for g in groups for c in g['Components']]
    if not all(isinstance(c.get('Id'),int) and isinstance(c.get('Type'),str) for c in components):raise ValueError('Unexpected component identity schema')
    report=dict(status='PKTMON_READONLY_INVENTORY_INDEPENDENTLY_VALIDATED',readonly=True,
        source_report_status=record['status'],source_report_sha256=digest(source),executed_script_sha256=record['script_sha256'],
        raw_evidence_sha256=hashes,actual_queries=3,actual_query_exit_codes=[q['exit_code'] for q in queries],
        ignored_empty_async_task_results=len(ignored),original_summary_preserved=True,
        capture_running_at_inventory=not capture_idle,existing_filters_empty=filters_empty,
        component_groups=len(groups),component_count=len(components),component_types=dict(collections.Counter(c['Type'] for c in components)),
        raw_utf8_and_component_json_valid=True,capture_started=False,filters_changed=False,network_settings_changed=False,
        pico_access=False,motor_commands=0,capture_permission_granted=False,
        scope='Point-in-time inventory only. Existing capture/filter state must be rechecked before any future capture. V3 script syntax fixed but not run as administrator.')
    with out.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
    (PRIVATE/'pktmon-inventory-selection.json').write_text(json.dumps(dict(run_id=args.run_id,raw_root=str(raw.absolute()),public_report=str(out.absolute()),validated=True),indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('raw_evidence_sha256','component_types')},indent=2))
    return 0

if __name__=='__main__':raise SystemExit(main())
