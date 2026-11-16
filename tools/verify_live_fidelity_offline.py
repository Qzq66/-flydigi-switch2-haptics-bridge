"""No-device verification of the streaming core, old A/B plan and frozen source."""
import argparse,hashlib,json,pathlib,sys,unittest
ROOT=pathlib.Path(__file__).absolute().parents[1]

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=pathlib.Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('Use a new evidence file')
    def guard(event,args):
        if event.startswith('socket.') or event in ('ctypes.dlopen','subprocess.Popen','os.system'):raise RuntimeError('Offline streaming verification blocked I/O: '+event)
    sys.addaudithook(guard);sys.path.insert(0,str(ROOT/'tools'))
    loader=unittest.defaultTestLoader;suite=unittest.TestSuite()
    for pattern in ('test_live_fidelity_candidate.py','test_fidelity_ab.py','test_haptic_fidelity*.py'):suite.addTests(loader.discover(str(ROOT/'tools'),pattern=pattern))
    result=unittest.TextTestRunner(verbosity=1).run(suite)
    from test_live_fidelity_candidate import replay
    traces=[replay(stamp,delay) for stamp in ('20261024-131624','20261024-132744') for delay in (0.,.016,.032)]
    manifest=json.loads((ROOT/'docs/FIDELITY_AB_BASELINE_2026-10-24.json').read_text());frozen={x['path']:x['sha256'] for x in manifest['files']}
    legacy=('handoff/2026-10-22/work/bridge_render.py','handoff/2026-10-22/work/bridge-switch-live.py','tools/run_v042_input_recheck.py','tools/run_fidelity_ab.py')
    for name in legacy:
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=frozen[name]:raise ValueError('Existing hardware entry changed: '+name)
    names=['tools/live_fidelity_candidate.py','tools/test_live_fidelity_candidate.py','tools/verify_live_fidelity_offline.py','tools/haptic_fidelity_candidate.py','handoff/2026-10-22/work/switch_hd_decode.py']+list(legacy)
    report=dict(status='PASSED_STREAMING_FIDELITY_CORE_OFFLINE' if result.wasSuccessful() else 'FAILED',tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),
        device_access=False,network_access=False,io_guard=True,live_hardware_entry_connected=False,physical_streaming_fidelity_validated=False,
        legacy_hardware_entries_unchanged=True,trace_replays=traces,
        limits=dict(gain=96,maximum_offset=12,sample_rate_hz=1000,jitter_buffer_ms=64,heartbeat_timeout_ms=80,source_group_ms_assumed=5,
            maximum_bilateral_episodes=1,maximum_active_ms_per_side=320,maximum_squared_code_sum_per_side=8000,maximum_armed_seconds=15),
        source_sha256={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in names},
        scope='Core rendering only with synthetic packet timing and old real motor words; not actual Wi-Fi, Windows scheduling, actuator output or end-to-end input continuity')
    with a.report.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
    print(json.dumps({k:v for k,v in report.items() if k!='source_sha256'},indent=2));return 0 if result.wasSuccessful() else 1

if __name__=='__main__':raise SystemExit(main())
