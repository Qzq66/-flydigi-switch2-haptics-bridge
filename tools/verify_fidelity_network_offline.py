"""Guarded no-device verification of the captured real-network replay candidate."""
import argparse,ast,hashlib,json,pathlib,sys,unittest
ROOT=pathlib.Path(__file__).absolute().parents[1]

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=pathlib.Path,required=True);p.add_argument('--report',type=pathlib.Path,required=True);p.add_argument('--baseline-report');a=p.parse_args()
    if a.plan.exists() or a.report.exists():p.error('Use new immutable plan and report paths')
    def guard(event,args):
        if event.startswith('socket.') or event in ('ctypes.dlopen','subprocess.Popen','os.system'):raise RuntimeError('Offline network entry verification blocked I/O: '+event)
    sys.addaudithook(guard);sys.path.insert(0,str(ROOT/'tools'))
    from fidelity_network_session import build_network_plan,validate_network_plan,digest
    # Importing the CLI must not instantiate sockets, HID, Tk, or subprocesses.
    import run_fidelity_network
    names=('fidelity_network_session.py','fidelity_network_io.py','run_fidelity_network.py','fidelity_network_window.py','live_fidelity_candidate.py','test_fidelity_network.py','test_fidelity_network_io.py','verify_fidelity_network_offline.py')
    for name in names:ast.parse((ROOT/'tools'/name).read_text(encoding='utf-8'),filename=name)
    plan=build_network_plan(a.baseline_report);validate_network_plan(plan)
    loader=unittest.defaultTestLoader;suite=unittest.TestSuite()
    for pattern in ('test_fidelity_network*.py','test_live_fidelity_candidate.py','test_fidelity_ab.py','test_haptic_fidelity*.py'):suite.addTests(loader.discover(str(ROOT/'tools'),pattern=pattern))
    result=unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful():return 1
    frozen={x['path']:x['sha256'] for x in json.loads((ROOT/'docs/FIDELITY_AB_BASELINE_2026-10-24.json').read_text())['files']}
    legacy=('handoff/2026-10-22/work/bridge_render.py','handoff/2026-10-22/work/bridge-switch-live.py','tools/run_v042_input_recheck.py','tools/run_fidelity_ab.py','tools/fidelity_ab_plan.py','tools/fidelity_ab_window.py')
    for name in legacy:
        if digest(ROOT/name)!=frozen[name]:raise ValueError('Existing successful hardware entry changed: '+name)
    ram=ROOT/'build/pico-v043-120s-ram-snapshot/pico_pro_capture.uf2'
    if digest(ram)!=plan['ram_uf2_sha256']:raise ValueError('Reviewed private RAM image differs')
    with a.plan.open('x',encoding='utf-8') as f:json.dump(plan,f,indent=2)
    report=dict(status='PASSED_FIDELITY_NETWORK_ENTRY_OFFLINE',tests=result.testsRun,failures=0,errors=0,io_guard=True,
        device_access=False,network_access=False,ram_loaded=False,physical_output=False,flash_write=False,
        real_network_replay_validated=False,actual_switch_game_fidelity_validated=False,
        legacy_hardware_entries_unchanged=True,plan_sha256=digest(a.plan),source_words=len(plan['events']),source_duration_us=plan['events'][-1]['at_us'],
        reviewed_ram_file_hash_matches=True,source_sha256={str(pathlib.Path('tools')/n).replace('\\','/'):digest(ROOT/'tools'/n) for n in names},
        scope='Injected clock/lifecycle/failure tests and strict evidence gates; no actual Windows scheduling, network jitter, RAM boot, ENDLAB handshake or actuator output tested here.')
    with a.report.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
    print(json.dumps({k:v for k,v in report.items() if k!='source_sha256'},indent=2));return 0

if __name__=='__main__':raise SystemExit(main())
