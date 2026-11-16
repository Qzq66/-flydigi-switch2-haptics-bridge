"""Explicit no-actuator hardware diagnostic. Never enables, streams or stops motors."""
import argparse,datetime,importlib.util,json,pathlib,queue,subprocess,sys,threading,time
from passive_reply_policy_g30 import ROOT,build_plan,validate_plan,PassiveSession,collection_completed,digest
WORK=ROOT/'handoff/2026-10-22/work';PRIVATE=WORK/'private';sys.path.insert(0,str(WORK))

def child(plan_path,result_path,phase,liveness_path):
    report=dict(status='INCOMPLETE',motor_commands=0,output_frames=0,persistent_configuration_commands=0)
    client=thread=timer=None;stop_event=threading.Event();inbox=queue.Queue(maxsize=512);session=PassiveSession()
    def publish(state,**extra):phase.write_text(json.dumps(dict(phase=state,clock='monotonic',**extra)))
    try:
        plan=json.loads(plan_path.read_text());validate_plan(plan)
        from bridge_windows import XInputSource,TimerResolution
        from bridge_input import NEUTRAL
        from short_wait_transport import ShortWaitClient as Client
        from bridge_render import collect_frames
        from game_input_liveness import passed
        from wake_timing_probe import SleepProbe
        from reply_provenance_probe import ProvenanceClient
        live=json.loads(liveness_path.read_text());source=XInputSource()
        if not passed(live) or source.slot!=live['slot']:raise ValueError('Input precheck or slot mismatch')
        quiet=None;until=time.monotonic()+5
        while time.monotonic()<until:
            now=time.monotonic()
            if source()==NEUTRAL:
                if quiet is None:quiet=now
                if now-quiet>=.5:break
            else:quiet=None
            time.sleep(.01)
        else:raise ValueError('Release controls before discovery')
        selection=json.loads((PRIVATE/'rollback-selection.json').read_text())
        saved=json.loads((pathlib.Path(selection['root'])/'work/private/bridge-session.json').read_text(encoding='utf-8-sig'))
        spec=importlib.util.spec_from_file_location('accepted_passive_discovery',WORK/'bridge-switch-live.py')
        discovery=importlib.util.module_from_spec(spec);spec.loader.exec_module(discovery)
        publish('DISCOVERING');ip=discovery.discover(int(saved['session'],16),plan['discovery_seconds'])
        def measured_neutral_input():
            source()  # Exercise the read cost; never forward controls to the host.
            return NEUTRAL
        report['input_mode']='read_xinput_then_send_fixed_neutral'
        sleep_probe=SleepProbe()
        client=ProvenanceClient(Client(ip,int(saved['session'],16),input_source=measured_neutral_input),sleep_probe=sleep_probe)
        def collect():
            try:collect_frames(client,inbox.put_nowait,stop_event.is_set,pause=sleep_probe)
            except BaseException as exc:
                try:inbox.put_nowait(exc)
                except queue.Full:stop_event.set()
        thread=threading.Thread(target=collect,daemon=True);thread.start();timer=TimerResolution()
        if not timer.start():raise RuntimeError('Timer acquisition failed')
        until=time.perf_counter()+5
        while not session.upstream_seen:
            frame=inbox.get(timeout=max(.001,until-time.perf_counter()))
            if isinstance(frame,BaseException):raise frame
            session.feed(frame)
        started=time.perf_counter();publish('PASSIVE_COLLECTING')
        while time.perf_counter()-started<plan['host_seconds']:
            while not inbox.empty():
                frame=inbox.get_nowait()
                if isinstance(frame,BaseException):raise frame
                session.feed(frame)
            if stop_event.is_set():raise RuntimeError('Collector stopped unexpectedly')
            session.tick(time.perf_counter())
            if session.terminal:break
            time.sleep(.001)
        if not session.terminal:raise TimeoutError('Passive terminal handshake incomplete')
        thread.join(1);report.update(terminal_ack_replied=client.terminal_ack_replied,collector_ended=not thread.is_alive())
    except BaseException as exc:report['error']=repr(exc)
    finally:
        if 'started' in locals():report['live_elapsed_seconds']=time.perf_counter()-started
        stop_event.set();errors=[]
        def finalize(label,action):
            try:action()
            except BaseException as exc:errors.append(label+': '+repr(exc))
        if thread:finalize('collector join',lambda:thread.join(1))
        if client:
            report['receive_wait_policy']=dict(budget_seconds=client.receive_budget,deadline_expirations=client.deadline_expirations,late_matching_replies=client.late_matching_replies,stale_replies=client.stale_replies)
            report['transport_diagnostics']=client.snapshot();finalize('transport close',client.close)
        if timer:finalize('timer release',timer.close)
        report.update(session.summary());report['timer_released']=timer is None or not timer.active
        report['finalization_errors']=errors
        if collection_completed(report):report['status']='COMPLETED_PASSIVE_COLLECTION_PENDING_FLASH_LOG'
        finalize('phase close',lambda:publish('ENDED'))
        result_path.write_text(json.dumps(report,indent=2))
    return 0 if collection_completed(report) else 1

def play(plan_path,picotool):
    plan=json.loads(plan_path.read_text());validate_plan(plan)
    if sys.platform!='win32':raise RuntimeError('Windows adapter required')
    from bridge_windows import load_owner
    from bridge_process import communicate_bounded
    from v043_installation import verify_installed
    from listener_readiness import wait_for_discovery
    from game_input_liveness import passed
    stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    paths={n:PRIVATE/('passive-transport-'+n+'-'+stamp+'.json') for n in ('backup','child','phase','liveness')}
    record_path=pathlib.Path(json.loads((PRIVATE/'v043-install-selection.json').read_text())['record'])
    record=json.loads(record_path.read_text());owner=load_owner();safe=owner.safe;reader=backup=proc=None
    report=dict(status='INCOMPLETE',plan_sha256=digest(plan_path),motor_commands=0,persistent_configuration_commands=0,host_flash_write=False)
    try:
        verified=verify_installed(record_path,picotool,record['pico_serial']);report['firmware_preflight']=verified
        if (not verified['verified'] or verified['baseline_generation']!=plan['expected_flash_generation']
            or verified['installed_snapshot_sha256']!=plan['expected_full_flash_sha256'] or verified['firmware_sha256']!=plan['firmware_sha256']):raise ValueError('Explicit passive baseline mismatch')
        hotspot=json.loads(subprocess.check_output(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(ROOT/'tools/read_hotspot_state.ps1')],text=True));report['hotspot_preflight']=hotspot
        if hotspot.get('hotspot_state')!='On' or hotspot.get('band')!='TwoPointFourGigahertz' or hotspot.get('iphone_usb_source') is not True:raise ValueError('Existing iPhone USB / 2.4GHz hotspot required')
        print('PASSIVE_PC_INPUT_CHECK; Pico stays on PC; follow read-only A/B window',flush=True)
        check=subprocess.Popen([sys.executable,str(ROOT/'tools/game_input_liveness.py'),str(paths['liveness'])],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
        _,_,killed=communicate_bounded(check,55)
        report['pc_input_liveness']=json.loads(paths['liveness'].read_text()) if paths['liveness'].exists() else {}
        if killed or check.returncode or not passed(report['pc_input_liveness']):raise ValueError('Actual PC input precheck failed')
        reader=safe.open_reader({});backup=owner.backup(reader,paths['backup']);reader.close();reader=None
        proc=subprocess.Popen([sys.executable,str(pathlib.Path(__file__).absolute()),'--child',str(plan_path),*[str(paths[k]) for k in ('child','phase','liveness')]],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
        began=time.monotonic();wait_for_discovery(proc,paths['phase']);report['post_neutral_discovery_ready']=True
        (PRIVATE/'passive-transport-listener-ready.json').write_text(json.dumps(dict(stamp=stamp,child_pid=proc.pid,post_neutral_discovery_ready=True)))
        print('PASSIVE_DISCOVERY_READY; await explicit USB-swap instruction; no motor output path',flush=True)
        _,stderr,killed=communicate_bounded(proc,max(.001,plan['guardian_seconds']-(time.monotonic()-began)))
        report.update(child_exit=proc.returncode,guardian_killed_child=killed,child_stderr=stderr[-1500:])
        if paths['child'].exists():report['child']=json.loads(paths['child'].read_text())
        reader=safe.open_reader({});owner.verify(reader,backup,report)
        if (collection_completed(report.get('child',{})) and proc.returncode==0 and not killed and report.get('configuration_unchanged') is True):report['status']='COMPLETED_PASSIVE_PROGRAM_PENDING_FLASH_LOG'
    except BaseException as exc:report['error']=repr(exc).replace(record['pico_serial'],'[private board]')
    finally:
        errors=[]
        def finalize(label,action):
            try:action()
            except BaseException as exc:errors.append(label+': '+repr(exc).replace(record['pico_serial'],'[private board]'))
        if proc and proc.poll() is None:finalize('kill child',proc.kill);finalize('reap child',lambda:proc.wait(2))
        if reader:finalize('reader close',reader.close)
        finalize('HID exit',safe.ro.lib.hid_exit)
        report['finalization_errors']=errors
        if errors:report['status']='INCOMPLETE'
        out=ROOT/'docs'/('PASSIVE_TRANSPORT_RUN_'+stamp+'.json');out.write_text(json.dumps(report,indent=2))
        print(json.dumps({k:v for k,v in report.items() if k!='child'},indent=2));print(out)
    return 0 if report['status']=='COMPLETED_PASSIVE_PROGRAM_PENDING_FLASH_LOG' else 1

def main():
    parser=argparse.ArgumentParser(description=__doc__);group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--play',type=pathlib.Path);group.add_argument('--child',nargs=4,type=pathlib.Path);parser.add_argument('--picotool',type=pathlib.Path)
    args=parser.parse_args()
    if args.child:return child(*args.child)
    if not args.picotool:parser.error('--play requires --picotool')
    return play(args.play,args.picotool)

if __name__=='__main__':raise SystemExit(main())
