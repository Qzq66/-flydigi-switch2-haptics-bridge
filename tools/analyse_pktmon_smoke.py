"""Analyse private smoke PCAPNG; no network/driver access or raw payload export."""
import argparse,hashlib,json,pathlib,re,struct
from pcapng_experiment import packets,udp_payload
from capture_clock import map_to_utc
ROOT=pathlib.Path(__file__).absolute().parents[1]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run-id',required=True);args=parser.parse_args()
    if not re.fullmatch(r'\d{8}-\d{6}',args.run_id):parser.error('Invalid run identifier')
    folder=ROOT/'handoff/2026-10-22/work/private'/('pktmon-smoke-'+args.run_id)
    public=ROOT/'docs'/('PKTMON_SMOKE_'+args.run_id+'.json')
    out=ROOT/'docs'/('PKTMON_SMOKE_ANALYSIS_'+args.run_id+'.json')
    if out.exists():raise ValueError('Keep immutable evidence')
    report=dict(status='INCOMPLETE',pico_access=False,motor_commands=0,original_delay_cause_proven=False)
    try:
        helper=json.loads(public.read_text(encoding='utf-8-sig'));sender=json.loads((folder/'sender.json').read_text())
        if helper['status']!='PKTMON_SMOKE_ARTIFACTS_READY_NOT_YET_ANALYSED':raise ValueError('Helper did not confirm bounded capture and cleanup')
        expected=b'CLK1';observations=[];scope_packets=0;hashes={}
        for name in ('packets.pcapng','drops.pcapng'):
            path=folder/name;data=path.read_bytes();hashes[name]=hashlib.sha256(data).hexdigest()
            for packet in packets(data):
                payload=udp_payload(packet)
                if payload is None:continue
                scope_packets+=1
                if len(payload)!=23 or payload[:4]!=expected or payload[8:]!=args.run_id.encode('ascii'):continue
                if packet['truncated'] or packet['reported_drops']:raise ValueError('Truncated smoke packet or reported capture loss')
                sequence=struct.unpack_from('<I',payload,4)[0]
                if sequence not in (0,1,2):raise ValueError('Unexpected smoke sequence')
                send=sender['sent'][sequence];begin=map_to_utc(send['begin_perf'],sender['anchors'])
                delta=packet['timestamp_ns']-begin
                if abs(delta)>5_000_000_000:raise ValueError('Capture clock does not match UTC anchors')
                observations.append(dict(sequence=sequence,file=name,section=packet['section'],interface=packet['interface'],direction=packet['direction'],timestamp_quantum_ns=packet['timestamp_quantum_ns'],component_observation_minus_send_begin_ns=delta))
        seen={item['sequence'] for item in observations}
        checks=dict(helper_capture_started=helper['capture_started'],helper_capture_stopped=helper['capture_stopped'],own_filter_removed=helper['filter_removed'],no_cleanup_errors=not helper['cleanup_errors'],
            three_diagnostic_sends=len(sender['sent'])==3 and [x['sequence'] for x in sender['sent']]==[0,1,2],all_three_observed=seen=={0,1,2},clock_anchors_usable=bool(observations),
            no_pico_or_motor_access=sender['motor_commands']==0 and sender['pico_access'] is False and helper['motor_commands']==0 and helper['pico_access'] is False)
        report.update(checks=checks,observations=observations,matching_copies=len(observations),experiment_scope_packets=scope_packets,private_capture_sha256=hashes,
            source_report_sha256=hashlib.sha256(public.read_bytes()).hexdigest(),sender_sha256=hashlib.sha256((folder/'sender.json').read_bytes()).hexdigest(),
            scope='Three outbound non-controller packets only, across available Windows components. Duplicate copies are not retransmissions. UTC epoch/units checked, not microsecond accuracy or incoming receive scheduling validated.')
        if all(checks.values()):report['status']='PASSED_BOUNDED_CAPTURE_CLOCK_SMOKE_AND_CLEANUP'
    except Exception as exc:report['error']=repr(exc)
    with out.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
    print(json.dumps({k:v for k,v in report.items() if k!='observations'},indent=2));return 0 if report['status'].startswith('PASSED_') else 1

if __name__=='__main__':raise SystemExit(main())
