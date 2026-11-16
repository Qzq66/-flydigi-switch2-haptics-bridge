"""Reproducible, guarded offline verification; never runs the hardware entry."""
import ast,hashlib,json,pathlib,sys,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]

def main():
    def guard(event,args):
        if event.startswith('socket.') or event in ('ctypes.dlopen','subprocess.Popen','os.system'):raise RuntimeError('Offline I/O blocked: '+event)
    sys.addaudithook(guard);sys.path.insert(0,str(ROOT/'tools'))
    from fidelity_game_policy_gap42 import build_game_plan,validate_game_plan
    from fidelity_game_policy_pcm41 import build_game_plan as previous_plan
    from phase_gap_probe import PhaseGapProbe
    from phase_gap_validation import assess_phase_gap
    from test_phase_gap_probe import Clock
    names=('phase_gap_probe.py','phase_gap_validation.py','fidelity_game_policy_gap42.py','run_fidelity_game_gap42.py','assess_fidelity_game_gap42.py','test_phase_gap_probe.py','test_phase_gap_integration.py')
    for n in names:ast.parse((ROOT/'tools'/n).read_text(encoding='utf-8'))
    new=(ROOT/'tools/run_fidelity_game_gap42.py').read_text(encoding='utf-8')
    restored=new.replace('from fidelity_game_policy_gap42 import','from fidelity_game_policy_pcm41 import')
    restored=restored.replace('from phase_gap_probe import GapObservedClient','from game_transport_diagnostics import ObservedClient').replace('client=GapObservedClient(Client(','client=ObservedClient(Client(')
    restored=restored.replace('collect_frames(client,inbox.put_nowait,stop.is_set,pause=client.pause)','collect_frames(client,inbox.put_nowait,stop.is_set)')
    if restored!=(ROOT/'tools/run_fidelity_game_pcm41.py').read_text(encoding='utf-8'):raise ValueError('Unexpected runner changes')
    plan=build_game_plan();validate_game_plan(plan);old=previous_plan()
    allowed={'version','expected_flash_generation','expected_full_flash_sha256','baseline_proof_sha256','scope','tool_sha256'}
    if any(plan[k]!=v for k,v in old.items() if k not in allowed):raise ValueError('Existing behavior/guard parameters changed')
    if plan['expected_flash_generation']!=42:raise ValueError('Expected42 candidate')
    for field in ('baseline','budget','heartbeat'):
        bad=json.loads(json.dumps(plan))
        if field=='baseline':bad['expected_flash_generation']=41
        elif field=='budget':bad['phase_observation']['max_events']=999999
        else:bad['limits']['heartbeat_seconds']=.090
        try:validate_game_plan(bad)
        except ValueError:pass
        else:raise ValueError('Tampered plan accepted')
    if assess_phase_gap({})['passed']:raise ValueError('Missing observations accepted')
    suite=unittest.TestSuite();loader=unittest.defaultTestLoader
    patterns=('test_phase_gap_probe.py','test_phase_gap_integration.py','test_written_pcm_probe.py','test_fidelity_game_g23.py','test_passive_transport.py','test_fidelity_game.py','test_game_input_liveness.py','test_game_transport_diagnostics.py','test_fidelity_network*.py','test_live_fidelity_candidate.py','test_fidelity_ab.py','test_haptic_fidelity*.py','test_listener_readiness.py')
    for pattern in patterns:suite.addTests(loader.discover(str(ROOT/'tools'),pattern=pattern))
    result=unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful():return 1
    clock=Clock();probe=PhaseGapProbe(clock)
    for i in range(1000):
        probe.begin('poll');clock.now+=.06 if i%11==0 else .001
        probe.finish(frame=dict(received_at=clock(),source_us=round(clock()*1e6)&0xffffffff,flags=7,events=[]),ended_at=clock())
        probe.begin('pause',.004);clock.now+=.016;probe.finish(ended_at=clock())
    sample=probe.snapshot();sample_bytes=len(json.dumps(sample,separators=(',',':')).encode())
    if sample_bytes>262144:raise ValueError('Synthetic snapshot size bound')
    planpath=ROOT/'docs/FIDELITY_GAP42_PLAN_2026-10-27.json'
    reportpath=ROOT/'docs/FIDELITY_GAP42_OFFLINE_2026-10-27.json'
    if planpath.exists() or reportpath.exists():raise ValueError('Preserve previous plan/reports')
    with planpath.open('x',encoding='utf-8') as f:json.dump(plan,f,indent=2)
    report=dict(status='PASSED_GAP42_OFFLINE_ONLY',tests=result.testsRun,io_guard=True,hardware_access=False,hardware_validated=False,
        runner_delta_checked=True,existing_parameters_unchanged=True,unsafe_plan_rejected=True,missing_detail_rejected=True,
        synthetic_events=2000,synthetic_compact_snapshot_bytes=sample_bytes,maximum_compact_snapshot_bytes=262144,
        plan_sha256=hashlib.sha256(planpath.read_bytes()).hexdigest())
    with reportpath.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
    print(json.dumps(report,indent=2));return 0

if __name__=='__main__':raise SystemExit(main())
