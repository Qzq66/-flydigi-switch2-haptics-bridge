"""Offline-only verification of the independently bound RTT45 entry."""
import ast,hashlib,json,pathlib,sys,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
def main():
    def guard(event,args):
        if event.startswith('socket.') or event in ('ctypes.dlopen','subprocess.Popen','os.system'):raise RuntimeError('Offline I/O forbidden: '+event)
    sys.addaudithook(guard);sys.path.insert(0,str(ROOT/'tools'))
    from fidelity_game_policy_rtt45 import build_game_plan,validate_game_plan
    from fidelity_game_policy_gap42 import build_game_plan as previous_plan
    from phase_gap_validation_v2 import assess_phase_gap
    from phase_gap_probe_v2 import PhaseGapProbe
    from test_phase_gap_probe import Clock
    names=('phase_gap_probe_v2.py','phase_gap_validation_v2.py','fidelity_game_policy_rtt45.py','run_fidelity_game_rtt45.py','assess_fidelity_game_rtt45.py','test_phase_gap_probe_v2.py','test_phase_gap_integration_v2.py','verify_rtt45_offline.py')
    for name in names:ast.parse((ROOT/'tools'/name).read_text(encoding='utf-8'))
    new=(ROOT/'tools/run_fidelity_game_rtt45.py').read_text()
    restored=new.replace('from fidelity_game_policy_rtt45 import','from fidelity_game_policy_gap42 import').replace('from phase_gap_probe_v2 import','from phase_gap_probe import')
    assert restored==(ROOT/'tools/run_fidelity_game_gap42.py').read_text(),'Unexpected runner behavior change'
    plan=build_game_plan();validate_game_plan(plan);old=previous_plan()
    allowed={'version','expected_flash_generation','expected_full_flash_sha256','baseline_proof_sha256','scope','tool_sha256'}
    assert all(plan[k]==v for k,v in old.items() if k not in allowed),'Existing settings changed'
    for field in ('generation','heartbeat','schema'):
        bad=json.loads(json.dumps(plan))
        if field=='generation':bad['expected_flash_generation']=43
        elif field=='heartbeat':bad['limits']['heartbeat_seconds']=.090
        else:bad['rtt_observation']['schema_version']=1
        try:validate_game_plan(bad)
        except ValueError:pass
        else:raise AssertionError('Tampered plan accepted')
    assert not assess_phase_gap({})['passed']
    suite=unittest.TestSuite()
    patterns=('test_phase_gap_probe_v2.py','test_phase_gap_integration_v2.py','test_phase_gap_probe.py','test_phase_gap_integration.py','test_written_pcm_probe.py','test_fidelity_game_g23.py','test_passive_transport.py','test_fidelity_game.py','test_game_input_liveness.py','test_game_transport_diagnostics.py','test_fidelity_network*.py','test_live_fidelity_candidate.py','test_fidelity_ab.py','test_haptic_fidelity*.py','test_listener_readiness.py')
    for pattern in patterns:suite.addTests(unittest.defaultTestLoader.discover(str(ROOT/'tools'),pattern=pattern))
    result=unittest.TextTestRunner().run(suite)
    if not result.wasSuccessful():return 1
    clock=Clock();probe=PhaseGapProbe(clock)
    for i in range(1000):
        probe.begin('poll');duration=.06 if i%11==0 else .001;clock.now+=duration
        probe.finish(frame=dict(received_at=clock(),source_us=i,flags=7,events=[],rtt_ms=duration*500),ended_at=clock())
        probe.begin('pause',.004);clock.now+=.016;probe.finish(ended_at=clock())
    size=len(json.dumps(probe.snapshot(),separators=(',',':'),allow_nan=False).encode())
    assert size<=262144
    report=dict(status='PASSED_RTT45_OFFLINE_ONLY',tests=result.testsRun,io_guard=True,hardware_access=False,hardware_validated=False,expected_generation=45,runner_delta_checked=True,existing_parameters_unchanged=True,tampered_plan_rejected=True,synthetic_compact_snapshot_bytes=size)
    docs=ROOT/'docs'
    for name,value in [('FIDELITY_RTT45_PLAN_2026-10-28.json',plan),('FIDELITY_RTT45_OFFLINE_2026-10-28.json',report)]:
        with (docs/name).open('x',encoding='utf-8') as f:json.dump(value,f,indent=2)
    freeze=dict(status='FROZEN_RTT45_OFFLINE_CANDIDATE',files=[dict(path='tools/'+n,sha256=hashlib.sha256((ROOT/'tools'/n).read_bytes()).hexdigest()) for n in names])
    with (docs/'FIDELITY_RTT45_PREPARATION_FREEZE_2026-10-28.json').open('x',encoding='utf-8') as f:json.dump(freeze,f,indent=2)
    print(json.dumps(report,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
