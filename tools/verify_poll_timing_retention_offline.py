"""Offline check of worst-gap retention, with the hardware-run sources unchanged."""
import hashlib,json,pathlib,sys,unittest
ROOT=pathlib.Path(__file__).absolute().parents[1]

def main():
    out=ROOT/'docs/POLL_TIMING_RETENTION_V2_OFFLINE_2026-10-25.json'
    if out.exists():raise ValueError('Use a new report path')
    def guard(event,args):
        if event.startswith('socket.') or event in ('ctypes.dlopen','subprocess.Popen','os.system'):raise RuntimeError('Offline I/O blocked: '+event)
    sys.addaudithook(guard);sys.path.insert(0,str(ROOT/'tools'))
    from passive_timing_policy_g24 import validate_plan
    validate_plan(json.loads((ROOT/'docs/PASSIVE_POLL_TIMING_PLAN_2026-10-25_G24.json').read_text()))
    suite=unittest.TestSuite();loader=unittest.defaultTestLoader
    for name in ('test_poll_timing_probe.py','test_poll_timing_probe_v2.py'):suite.addTests(loader.discover(str(ROOT/'tools'),pattern=name))
    result=unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful():return 1
    names=('poll_timing_probe_v2.py','test_poll_timing_probe_v2.py','verify_poll_timing_retention_offline.py','poll_timing_probe.py')
    report=dict(status='PASSED_CRITICAL_AND_WORST_GAP_RETENTION_OFFLINE',tests=result.testsRun,failures=0,errors=0,io_guard=True,
        device_access=False,network_access=False,motor_output=False,hardware_validated=False,recorded_hardware_probe_source_unchanged=True,
        source_sha256={('tools/'+n):hashlib.sha256((ROOT/'tools'/n).read_bytes()).hexdigest() for n in names},
        scope='Separate V2 probe preserves critical events and worst gap with preceding context. Not yet wired to a new generation25 hardware plan.')
    with out.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
    print(json.dumps({k:v for k,v in report.items() if k!='source_sha256'},indent=2));return 0

if __name__=='__main__':raise SystemExit(main())
