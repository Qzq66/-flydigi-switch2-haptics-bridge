"""Offline phase and packet coverage checks for a completed pacing run."""
import argparse,hashlib,json,pathlib,re
from analyse_capacity_timing import stats
from component_receive_analysis_v3 import correlate
ROOT=pathlib.Path(__file__).resolve().parents[1]
def main():
    p=argparse.ArgumentParser();p.add_argument('--run-id',required=True);a=p.parse_args()
    if not re.fullmatch(r'\d{8}-\d{6}',a.run_id):p.error('Invalid run ID')
    folder=ROOT/'handoff/2026-10-22/work/private'/('pktmon-ram-capacity-'+a.run_id)
    app_path=ROOT/'docs'/('RAM_PACING_PATH_'+a.run_id+'.json')
    app=json.loads(app_path.read_text());helper=json.loads((ROOT/'docs'/('PKTMON_RAM_CAPACITY_'+a.run_id+'.json')).read_text())
    assert app['status']=='BOUNDED_RAM_POLLING_FLASH_UNCHANGED_PENDING_CAPTURE_ANALYSIS'
    assert helper['capture_stopped'] and helper['filter_removed'] and not helper['cleanup_errors']
    raw=(folder/'poll-phases.json').read_bytes();packet_raw=(folder/'application-packets.json').read_bytes()
    assert hashlib.sha256(raw).hexdigest()==app['phase_trace']['sha256']
    assert hashlib.sha256(packet_raw).hexdigest()==app['packet_clock']['private_trace_sha256']
    phases=json.loads(raw);trace=json.loads(packet_raw);rows=phases['rows']
    sends=[r for r in trace['rows'] if r['direction']=='send']
    assert not phases['overflow'] and len(rows)==len(sends)==app['polling']['poll_calls']
    for i,(r,s) in enumerate(zip(rows,sends)):
        assert r['index']==i and r['poll_start']<=s['at']<=r['poll_end']<=r['sleep_start']<=r['sleep_end']
        if i:assert rows[i-1]['sleep_end']<=r['poll_start']
    poll=[(r['poll_end']-r['poll_start'])*1e9 for r in rows]
    sleep=[(r['sleep_end']-r['sleep_start'])*1e9 for r in rows]
    between=[(b['poll_start']-a['sleep_end'])*1e9 for a,b in zip(rows,rows[1:])]
    full=correlate(trace,(folder/'packets.pcapng').read_bytes())
    assert full['complete_receive_coverage'],'Capture coverage incomplete'
    report=dict(status='PASSED_PHASE_AND_RECEIVE_COVERAGE',hardware_access=False,motor_commands=0,
      poll_calls=len(rows),accepted_frames=app['polling']['accepted_frames'],
      poll_duration=stats(poll),actual_sleep_duration=stats(sleep),between_iterations=stats(between),
      requested_sleep_ms=4,maximum_phase_append_ms=phases['maximum_append_seconds']*1000,
      phase_sha256=hashlib.sha256(raw).hexdigest(),packet_trace_sha256=hashlib.sha256(packet_raw).hexdigest(),
      app_report_sha256=hashlib.sha256(app_path.read_bytes()).hexdigest(),full_capture=full,
      full_flash_after_matches=app['full_flash_after_matches'],
      limitations=['Instrumentation may perturb scheduling.','Poll duration includes receive, validation and packet recording.',
      'Sleep duration includes wakeup scheduling; not proof of a specific Windows timer cause.'])
    out=ROOT/'docs'/('RAM_PACING_ANALYSIS_'+a.run_id+'.json')
    with out.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
    print(json.dumps({k:v for k,v in report.items() if k!='full_capture'},indent=2))
if __name__=='__main__':main()
