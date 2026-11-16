"""No-device parser, clock and capture-helper preparation checks."""
import ast,hashlib,json,pathlib,sys,unittest
ROOT=pathlib.Path(__file__).absolute().parents[1]

def main():
    out=ROOT/'docs/PKTMON_CAPTURE_OFFLINE_2026-10-25.json'
    if out.exists():raise ValueError('Preserve existing report')
    def guard(event,args):
        if event.startswith('socket.') or event in ('ctypes.dlopen','subprocess.Popen','os.system'):raise RuntimeError('Offline I/O blocked: '+event)
    sys.addaudithook(guard);sys.path.insert(0,str(ROOT/'tools'))
    names=('capture_clock.py','pcapng_experiment.py','send_pktmon_smoke.py','analyse_pktmon_smoke.py','test_pktmon_capture.py','verify_pktmon_capture_offline.py')
    for name in names:ast.parse((ROOT/'tools'/name).read_text(encoding='utf-8'),filename=name)
    suite=unittest.TestSuite();loader=unittest.defaultTestLoader
    for name in ('test_pktmon_capture.py','test_reply_provenance_probe.py','test_wake_timing_probe.py'):
        suite.addTests(loader.discover(str(ROOT/'tools'),pattern=name))
    result=unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful():return 1
    previous=json.loads((ROOT/'docs/PKTMON_INVENTORY_FREEZE_20261025-205001.json').read_text())
    for item in previous['files']:
        if hashlib.sha256((ROOT/item['path']).read_bytes()).hexdigest()!=item['sha256']:raise ValueError('Old inventory source/evidence changed')
    ps=('pktmon_capture_common.ps1','run_pktmon_smoke.ps1','test_pktmon_capture_guards.ps1')
    report=dict(status='PASSED_PKTMON_CAPTURE_PARSER_CLOCK_OFFLINE',tests=result.testsRun,failures=0,errors=0,io_guard=True,
        device_access=False,network_access=False,driver_access=False,capture_started=False,filters_changed=False,motor_output=False,
        hardware_validated=False,previous_inventory_source_unchanged=True,
        source_sha256={('tools/'+n):hashlib.sha256((ROOT/'tools'/n).read_bytes()).hexdigest() for n in names+ps},
        scope='Synthetic PCAPNG/clock tests only. Admin helper syntax/guards checked separately; real capture and timestamp format remain unverified.')
    with out.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
    print(json.dumps({k:v for k,v in report.items() if k!='source_sha256'},indent=2));return 0

if __name__=='__main__':raise SystemExit(main())
