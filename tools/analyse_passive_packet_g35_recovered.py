"""Correlate completed private captures with same-process socket timestamps."""
import argparse,hashlib,json,pathlib,re
from component_receive_analysis_v2 import correlate
ROOT=pathlib.Path(__file__).absolute().parents[1]

def main():
    p=argparse.ArgumentParser();p.add_argument('--capture-run',required=True);p.add_argument('--program',type=pathlib.Path,required=True);p.add_argument('--conversion-proof',type=pathlib.Path,required=True);a=p.parse_args()
    if not re.fullmatch(r'\d{8}-\d{6}',a.capture_run):p.error('Invalid run')
    folder=ROOT/'handoff/2026-10-22/work/private'/('pktmon-passive-g35-'+a.capture_run)
    out=ROOT/'docs'/('PASSIVE_PACKET_G35_COMPONENTS_'+a.capture_run+'.json')
    if out.exists():raise ValueError('Keep original assessment')
    result=dict(status='INCOMPLETE',pico_access=False,motor_commands=0,original_network_delay_cause_proven=False,components=[])
    try:
        helper_path=ROOT/'docs'/('PKTMON_PASSIVE_G35_'+a.capture_run+'.json')
        helper=json.loads(helper_path.read_text());program=json.loads(a.program.read_text());child=program.get('child',{})
        trace_data=(folder/'application-packets.json').read_bytes();trace=json.loads(trace_data)
        expected=child.get('packet_clock',{})
        if expected.get('private_trace_sha256')!=hashlib.sha256(trace_data).hexdigest():raise ValueError('Application trace binding')
        if not (helper['capture_stopped'] and helper['filter_removed'] and not helper['cleanup_errors']):raise ValueError('Capture cleanup incomplete')
        conversion=json.loads(a.conversion_proof.read_text())
        if conversion['status']!='CONVERTED_EXISTING_STOPPED_ETL':raise ValueError('Offline conversion incomplete')
        if conversion['source_helper_sha256']!=hashlib.sha256(helper_path.read_bytes()).hexdigest():raise ValueError('Conversion helper binding')
        if conversion['source_etl_sha256']!=hashlib.sha256((folder/('packets-'+a.capture_run+'.etl')).read_bytes()).hexdigest():raise ValueError('ETL binding')
        converted=folder/'offline-conversion'
        for item in conversion['files']:
            if pathlib.Path(item['name']).name!=item['name'] or item['exit_code']!=0:raise ValueError('Invalid conversion item')
            if hashlib.sha256((converted/item['name']).read_bytes()).hexdigest()!=item['sha256']:raise ValueError('Converted file binding')
        result['original_helper_status']=helper['status']
        result['offline_conversion_proof_sha256']=hashlib.sha256(a.conversion_proof.read_bytes()).hexdigest()
        for component in helper['component_ids']:
            path=converted/('component-'+str(component)+'.pcapng')
            row=dict(component_id=component,capture_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            try:row.update(correlate(trace,path.read_bytes()))
            except Exception as exc:row['error']=repr(exc)
            result['components'].append(row)
        usable=[x for x in result['components'] if x.get('complete_receive_coverage') and x.get('negative_beyond_1ms')==0 and not x.get('error')]
        result.update(program_sha256=hashlib.sha256(a.program.read_bytes()).hexdigest(),helper_sha256=hashlib.sha256(helper_path.read_bytes()).hexdigest(),
            private_trace_sha256=hashlib.sha256(trace_data).hexdigest(),application_receive_rows=sum(x['direction']=='receive' for x in trace['rows']),
            application_observer_errors=trace['errors'],application_observer_overflow=trace['overflow'],maximum_observer_seconds=trace['maximum_observer_seconds'],
            complete_usable_component_count=len(usable),program_status=program['status'],configuration_unchanged=program.get('configuration_unchanged'),
            requires_same_trial_flash_readback=True,scope='Component point to socket return, including OS scheduling. No physical-air timing or absolute Pico/PC clock synchronization.')
        if (usable and program['status']=='COMPLETED_PASSIVE_PROGRAM_PENDING_FLASH_LOG' and program.get('configuration_unchanged') is True
            and child.get('motor_commands')==0 and not trace['errors'] and not trace['overflow']):
            result['status']='PACKET_COMPONENT_TIMING_PENDING_SAME_TRIAL_FLASH_READBACK'
    except Exception as exc:result['error']=repr(exc)
    with out.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='components'},indent=2))
    return 0 if result['status'].startswith('PACKET_COMPONENT_TIMING_') else 1

if __name__=='__main__':raise SystemExit(main())
