"""No-device offline verification of call-breakdown diagnostic entry."""
import ast,json,pathlib,sys,unittest,hashlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
def main():
    def guard(event,args):
        if event.startswith('socket.') or event in ('ctypes.dlopen','subprocess.Popen','os.system'):raise RuntimeError('Offline I/O blocked: '+event)
    sys.addaudithook(guard);sys.path.insert(0,str(ROOT/'tools'))
    from call_breakdown12_policy_g54 import build_plan,validate_plan
    from poll_call_breakdown import PollBreakdown
    from test_poll_call_breakdown import Clock
    plan=build_plan();validate_plan(plan)
    assert (ROOT/'tools/receive_budget12_transport.py').read_text().replace('.012','.06')==(ROOT/'handoff/2026-10-22/work/bridge_transport.py').read_text()
    assert (ROOT/'tools/run_call_breakdown12_g54.py').read_text().replace('from call_breakdown12_policy_g54 import','from call_breakdown_policy_g53 import').replace('from receive_budget12_transport import Client','from bridge_transport import Client')==(ROOT/'tools/run_call_breakdown_g53.py').read_text()
    assert plan['expected_flash_generation']==54 and plan['receive_timeout_seconds']==.012 and plan['motor_commands']==0
    bad=json.loads(json.dumps(plan));bad['expected_flash_generation']=53
    try:validate_plan(bad)
    except ValueError:pass
    else:raise AssertionError('Stale plan accepted')
    tree=ast.parse((ROOT/'tools/run_call_breakdown12_g54.py').read_text())
    child=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='child')
    for n in ast.walk(child):
        if isinstance(n,ast.Attribute):assert n.attr not in ('stream','mode','stop','waveform','open_reader','write_range')
    suite=unittest.TestSuite()
    patterns=('test_receive_budget12_single_variable.py','test_poll_call_breakdown.py','test_phase_gap_probe.py','test_phase_gap_integration.py','test_written_pcm_probe.py','test_fidelity_game_g23.py','test_passive_transport.py','test_fidelity_game.py','test_game_input_liveness.py','test_game_transport_diagnostics.py','test_fidelity_network*.py','test_live_fidelity_candidate.py','test_fidelity_ab.py','test_haptic_fidelity*.py','test_listener_readiness.py')
    for pattern in patterns:suite.addTests(unittest.defaultTestLoader.discover(str(ROOT/'tools'),pattern=pattern))
    result=unittest.TextTestRunner().run(suite)
    if not result.wasSuccessful():return 1
    clock=Clock();clock.now=0.;p=PollBreakdown(lambda:None,clock)
    for i in range(2000):
        p.begin()
        for kind in ('input_read','sendto','recvfrom'):
            def call():clock.now+=.02 if i%13==0 else .0005
            p.invoke(kind,call)
        p.finish(frame=dict(received_at=clock(),source_us=i,flags=7))
    size=len(json.dumps(p.snapshot(),separators=(',',':')).encode());assert size<=262144
    report=dict(status='PASSED_CALL_BREAKDOWN12G54_OFFLINE_ONLY',tests=result.testsRun,io_guard=True,hardware_access=False,hardware_validated=False,no_actuator_child_ast_checked=True,synthetic_polls=2000,synthetic_compact_bytes=size,maximum_compact_bytes=262144)
    for name,v in [('CALL_BREAKDOWN12_G54_PLAN_2026-10-28.json',plan),('CALL_BREAKDOWN12_G54_OFFLINE_2026-10-28.json',report)]:
        with (ROOT/'docs'/name).open('x',encoding='utf-8') as f:json.dump(v,f,indent=2)
    names=['receive_budget12_transport.py','test_receive_budget12_single_variable.py','poll_call_breakdown.py','poll_call_breakdown_validation.py','call_breakdown12_policy_g54.py','run_call_breakdown12_g54.py','test_poll_call_breakdown.py','verify_call_breakdown12_g54_offline.py']
    with (ROOT/'docs/CALL_BREAKDOWN12_G54_FREEZE_2026-10-28.json').open('x',encoding='utf-8') as f:json.dump(dict(files=[dict(path='tools/'+n,sha256=hashlib.sha256((ROOT/'tools'/n).read_bytes()).hexdigest()) for n in names]),f,indent=2)
    print(json.dumps(report,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
