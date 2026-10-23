"""Strict real-Switch input-only session; no actuator output in the child."""
import argparse,datetime,json,pathlib,subprocess,sys
ROOT=pathlib.Path(__file__).absolute().parents[1];WORK=ROOT/'handoff/2026-10-22/work';sys.path.insert(0,str(WORK))
from bridge_windows import load_owner
from bridge_process import communicate_bounded,input_end_check_succeeded,game_end_check_succeeded
from bridge_session_policy import session_limits
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--game-output',action='store_true');parser.add_argument('--staged-game',action='store_true');parser.add_argument('--live-seconds',type=int,choices=(60,120),default=60)
parser.add_argument('--firmware-record',type=pathlib.Path);parser.add_argument('--picotool',type=pathlib.Path);parser.add_argument('--pico-serial');parser.add_argument('--timed-input',action='store_true');parser.add_argument('--input-acceptance-bundle',type=pathlib.Path);options=parser.parse_args()
limits=session_limits(options.live_seconds);variant=limits['expected_firmware'].upper()
if options.staged_game and not options.game_output:parser.error('--staged-game requires --game-output')
if options.live_seconds==120 and (not options.firmware_record or not options.picotool or not options.pico_serial):parser.error('120s requires board-bound installation record and physical BOOTSEL verification')
if options.live_seconds==120 and options.game_output and (not options.staged_game or not options.input_acceptance_bundle):parser.error('120s output requires staged click and verified input acceptance bundle')
if options.timed_input and (options.live_seconds!=120 or options.game_output):parser.error('--timed-input requires 120s with output disabled')
stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S');private=WORK/'private'
selection=json.loads((private/'rollback-selection.json').read_text(encoding='utf-8'))
session=pathlib.Path(selection['root'])/'work/private/bridge-session.json'
bp=private/('v042-input-backup-'+stamp+'.json');cp=private/('v042-input-child-'+stamp+'.json')
report=dict(status='INCOMPLETE',actual_switch_test=True,game_test=options.game_output,input_check_only=not options.game_output,automatic_resume=False,motor_output_enabled=options.game_output and not options.staged_game,persistent_flydigi_commands=0,game_haptics_validated=False)
report['session_limits']=limits
owner=load_owner();safe=owner.safe;r=b=proc=ui=None;dirty=False
try:
    if options.live_seconds==120:
        from v043_installation import verify_installed
        report['firmware_preflight']=verify_installed(options.firmware_record,options.picotool,options.pico_serial)
        if options.game_output:
            from v043_game_gate import authorize
            report['input_acceptance_gate']=authorize(options.input_acceptance_bundle,report['firmware_preflight'])
    r=safe.open_reader(report);b=owner.backup(r,bp);r.close();r=None
    if options.live_seconds==120:
        hotspot=json.loads(subprocess.check_output(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(ROOT/'tools/read_hotspot_state.ps1')],text=True))
        report['hotspot_preflight']=hotspot
        if hotspot.get('hotspot_state')!='On' or hotspot.get('band')!='TwoPointFourGigahertz' or hotspot.get('iphone_usb_source') is not True:raise ValueError('Original 2.4GHz hotspot on iPhone USB must be active before listener starts')
    args=[sys.executable,str(WORK/'bridge-switch-live.py'),'--child',str(bp),str(cp),'--game-pilot','--prompt-ms','120','--prompt-offset','12','--input-check-only','--session-file',str(session)]
    args+=['--live-seconds',str(options.live_seconds)]
    if options.game_output:args.remove('--input-check-only')
    if options.timed_input:
        timing=private/('input-timing-'+stamp+'.json')
        if timing.exists():raise ValueError('Timing file already exists')
        args+=['--input-timing-file',str(timing)]
        report['timed_input']=True
        ui=subprocess.Popen([sys.executable,str(ROOT/'tools/input_timing_window.py'),str(timing)],creationflags=subprocess.CREATE_NO_WINDOW)
    if options.staged_game:
        arm=private/('game-arm-'+stamp+'.json');phase=private/('game-phase-'+stamp+'.json')
        if arm.exists() or phase.exists():raise ValueError('Staged session files already exist')
        args+=['--arm-file',str(arm),'--phase-status-file',str(phase)]
        report['staged_game']=True
        ui=subprocess.Popen([sys.executable,str(ROOT/'tools/game_arm_window.py'),str(arm),str(phase)],creationflags=subprocess.CREATE_NO_WINDOW)
    proc=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,creationflags=subprocess.CREATE_NO_WINDOW);dirty=True
    (private/'v042-listener-ready.json').write_text(json.dumps(dict(stamp=stamp,child_pid=proc.pid,started=True)),encoding='utf-8')
    print(('BOUNDED_GAME_LISTENER_STARTED; 120ms +/-12 prompts' if options.game_output else 'INPUT_ONLY_LISTENER_STARTED; no motor output')+'; keep buttons neutral until instructed',flush=True)
    _,stderr,killed=communicate_bounded(proc,limits['guardian_seconds']);report.update(child_exit=proc.returncode,guardian_killed_child=killed,child_stderr=stderr[-1500:])
    if cp.exists():report['child']=json.loads(cp.read_text(encoding='utf-8'))
    if options.staged_game:report['motor_output_enabled']=report.get('child',{}).get('motor_output_enabled',False)
    r=safe.open_reader(report);owner.identity(r,b);owner.stop(r,report);dirty=False;owner.verify(r,b,report)
    gate=game_end_check_succeeded if options.game_output else input_end_check_succeeded
    if not killed and gate(report.get('child'),proc.returncode) and report['runtime_disable_ack'] and report['configuration_unchanged']:
        report['status']='PASSED_'+variant+('_SWITCH_GAME_PROGRAM_CHECKS' if options.game_output else '_SWITCH_INPUT_END_PROGRAM_CHECKS')
except BaseException as exc:report['error']=repr(exc)
finally:
    if proc and proc.poll() is None:proc.kill();proc.wait(timeout=2)
    if b and dirty:
        try:
            if r is None:r=safe.open_reader(report)
            owner.identity(r,b);owner.stop(r,report);owner.verify(r,b,report)
        except BaseException as exc:report['cleanup_error']=repr(exc)
    if r:r.close()
    if ui and ui.poll() is None:ui.terminate();ui.wait(timeout=2)
    safe.ro.lib.hid_exit()
    output=ROOT/'docs'/('WINDOWS_'+variant+('_GAME_RECHECK_' if options.game_output else '_INPUT_RECHECK_')+stamp+'.json');output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='child'},indent=2));print(str(output))
raise SystemExit(0 if report['status']=='PASSED_'+variant+('_SWITCH_GAME_PROGRAM_CHECKS' if options.game_output else '_SWITCH_INPUT_END_PROGRAM_CHECKS') else 1)
