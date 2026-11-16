"""Check A/B plan and failure handling under I/O guards; never enables playback."""
import argparse,ast,hashlib,json,pathlib,sys,unittest
ROOT=pathlib.Path(__file__).absolute().parents[1]

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=pathlib.Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('Existing evidence must be preserved')
    def guard(event,args):
        if event.startswith('socket.') or event in ('ctypes.dlopen','subprocess.Popen','os.system'):raise RuntimeError('Offline A/B verification blocked I/O: '+event)
    sys.addaudithook(guard);sys.path.insert(0,str(ROOT/'tools'))
    loader=unittest.defaultTestLoader;suite=unittest.TestSuite()
    for pattern in ('test_fidelity_ab.py','test_haptic_fidelity*.py'):suite.addTests(loader.discover(str(ROOT/'tools'),pattern=pattern))
    result=unittest.TextTestRunner(verbosity=1).run(suite)
    sources=[ROOT/'tools'/name for name in ('fidelity_ab_plan.py','run_fidelity_ab.py','fidelity_ab_window.py','test_fidelity_ab.py','haptic_fidelity_candidate.py','test_haptic_fidelity_candidate.py','audit_haptic_fidelity.py','test_haptic_fidelity_audit.py','verify_fidelity_ab_offline.py')]
    for path in sources:ast.parse(path.read_text(encoding='utf-8'))
    from fidelity_ab_plan import build_plan
    plan=build_plan()
    report=dict(status='PASSED_OFFLINE_FIDELITY_AB_ENTRY' if result.wasSuccessful() else 'FAILED',tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),
        io_guard=True,device_access=False,network_access=False,playback_started=False,physical_ab_validated=False,
        source_sha256={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
        comparison=[dict(label=s['label'],samples_per_side=s['samples_per_side'],peak_code=s['peak_code'],squared_code_sum=s['squared_code_sum']) for s in plan['segments']],
        total_samples_per_side=plan['total_samples_per_side'],squared_code_sum_per_side=plan['squared_code_sum_per_side'],
        scope='Deterministic source-bound clips, no-catchup scheduler, guaranteed stop attempts, complete-frame/stop/gap/manual acceptance. Fake callbacks do not prove HID/guardian behavior on hardware.')
    with a.report.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
    print(json.dumps({k:v for k,v in report.items() if k!='source_sha256'},indent=2))
    return 0 if result.wasSuccessful() else 1

if __name__=='__main__':raise SystemExit(main())
