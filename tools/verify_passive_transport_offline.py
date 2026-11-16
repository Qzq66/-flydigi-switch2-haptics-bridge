"""Build immutable passive plan with no-device audit and existing regressions."""
import argparse,ast,json,pathlib,sys,unittest
ROOT=pathlib.Path(__file__).absolute().parents[1]

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=pathlib.Path,required=True);p.add_argument('--report',type=pathlib.Path,required=True);a=p.parse_args()
    if a.plan.exists() or a.report.exists():p.error('Use new immutable paths')
    def guard(event,args):
        if event.startswith('socket.') or event in ('ctypes.dlopen','subprocess.Popen','os.system'):raise RuntimeError('Offline I/O blocked: '+event)
    sys.addaudithook(guard);sys.path.insert(0,str(ROOT/'tools'))
    import run_passive_transport
    from passive_transport_policy import build_plan,validate_plan,digest
    names=('passive_transport_policy.py','run_passive_transport.py','test_passive_transport.py','verify_passive_transport_offline.py')
    for name in names:ast.parse((ROOT/'tools'/name).read_text(encoding='utf-8'),filename=name)
    plan=build_plan();validate_plan(plan);suite=unittest.TestSuite();loader=unittest.defaultTestLoader
    for pattern in ('test_passive_transport.py','test_fidelity_game.py','test_game_input_liveness.py','test_game_transport_diagnostics.py',
        'test_fidelity_network*.py','test_live_fidelity_candidate.py','test_fidelity_ab.py','test_haptic_fidelity*.py','test_listener_readiness.py'):
        suite.addTests(loader.discover(str(ROOT/'tools'),pattern=pattern))
    result=unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful():return 1
    old=json.loads((ROOT/'docs/FIDELITY_GAME_ENTRY_OFFLINE_2026-10-25_G22_DIAGNOSTIC.json').read_text())
    for name,h in old['source_sha256'].items():
        if digest(ROOT/name)!=h:raise ValueError('Previous diagnostic candidate source changed: '+name)
    with a.plan.open('x',encoding='utf-8') as f:json.dump(plan,f,indent=2)
    report=dict(status='PASSED_PASSIVE_TRANSPORT_OFFLINE',tests=result.testsRun,failures=0,errors=0,io_guard=True,
        device_access=False,network_access=False,motor_output=False,firmware_loaded=False,hardware_validated=False,
        previous_game_diagnostic_source_unchanged=True,plan_sha256=digest(a.plan),source_sha256={('tools/'+n):digest(ROOT/'tools'/n) for n in names})
    with a.report.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
    print(json.dumps({k:v for k,v in report.items() if k!='source_sha256'},indent=2));return 0

if __name__=='__main__':raise SystemExit(main())
