"""Run candidate simulation and related gates under accidental hardware-I/O guards."""
import argparse,hashlib,json,pathlib,sys,unittest
ROOT=pathlib.Path(__file__).absolute().parents[1]
TOOLS=ROOT/'tools';WORK=ROOT/'handoff/2026-10-22/work'

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=pathlib.Path,required=True)
    args=parser.parse_args()
    if args.report.exists():parser.error('Existing evidence must not be overwritten')
    def guard(event,values):
        if event.startswith('socket.') or event in ('ctypes.dlopen','subprocess.Popen','os.system'):
            raise RuntimeError('Offline verification blocked I/O: '+event)
        if event=='import' and values[0] in ('xinput_readonly','hid','hidapi'):
            raise RuntimeError('Offline verification blocked hardware module: '+values[0])
    sys.addaudithook(guard);sys.path.insert(0,str(TOOLS));sys.path.insert(0,str(WORK))
    names=('test_repeated_game_events','test_repeated_game_assessment','test_listener_readiness','test_game_output_latch','test_game_phase','test_game_end_gate','test_v043_game_assessment','test_v043_game_gate')
    suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in names)
    result=unittest.TextTestRunner(verbosity=1).run(suite)
    sources=[TOOLS/(name+'.py') for name in names]
    sources += [pathlib.Path(__file__),TOOLS/'assess_v043_staged_game.py',TOOLS/'repeated_event_evidence.py',TOOLS/'listener_readiness.py',TOOLS/'game_scenarios.py',TOOLS/'game_arm_window.py',TOOLS/'run_v042_input_recheck.py',TOOLS/'v043_game_gate.py']
    sources += [WORK/name for name in ('bridge_render.py','bridge_input.py','bridge_process.py','bridge_game_phase.py','bridge-switch-live.py','switch_hd_decode.py')]
    report=dict(status='PASSED_REPEATED_EVENT_OFFLINE_CANDIDATE' if result.wasSuccessful() else 'FAILED',
        hardware_access=False,network_access=False,io_guard=True,synthetic_time=True,hardware_multi_event_validated=False,
        tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),
        modules=list(names),source_sha256={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
        scope='Two synthetic bilateral events separated by 5 seconds, pre-arm silence, fourth-edge cap, input conversion after mute and disable cancellation; not physical transport or actuator evidence')
    with args.report.open('x',encoding='utf-8') as out:json.dump(report,out,indent=2)
    print(json.dumps({k:v for k,v in report.items() if k!='source_sha256'},indent=2))
    return 0 if result.wasSuccessful() else 1

if __name__=='__main__':raise SystemExit(main())
