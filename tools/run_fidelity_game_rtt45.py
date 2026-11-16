"""Independent live-Switch dual-band candidate; --prepare performs no I/O to devices."""
import argparse,datetime,importlib.util,json,pathlib,queue,subprocess,sys,threading,time
from fidelity_game_policy_rtt45 import ROOT,build_game_plan,validate_game_plan,GameSession,game_child_passed,game_parent_passed,digest
WORK=ROOT/'handoff/2026-10-22/work';PRIVATE=WORK/'private';sys.path.insert(0,str(WORK))

def child(plan_path,backup_path,result_path,phase,arm):
    report=dict(status='INCOMPLETE',host_flash_write=False,persistent_flydigi_commands=0,actual_switch_game=True)
    reader=client=thread=timer=game=pcm=None;stop=threading.Event();inbox=queue.Queue(maxsize=512)
    source=None;reads=0;counts_at_stop=None;phase_name='DISCOVERING';deadline=None
    fault_observed=False
    def publish(state,**extra):phase.write_text(json.dumps(dict(phase=state,clock='monotonic',**extra)))
    def cancelled():return arm.with_suffix('.cancel').exists()
    try:
        plan=json.loads(plan_path.read_text());validate_game_plan(plan)
        from bridge_windows import load_owner,TimerResolution,XInputSource
        from bridge_input import NEUTRAL
        from bridge_transport import Client
        from bridge_render import collect_frames
        owner=load_owner();safe=owner.safe;b=json.loads(backup_path.read_text());reader=safe.open_reader({});owner.identity(reader,b)
        check={};owner.verify(reader,b,check)
        if not check['configuration_unchanged']:raise ValueError('Configuration changed before game')
        reader.allowed_modes=owner.MODES;reader.maximum_offset=12;source=XInputSource()
        liveness=json.loads(backup_path.with_name(backup_path.name.replace('backup','liveness')).read_text())
        from game_input_liveness import passed as liveness_passed
        if not liveness_passed(liveness) or source.slot!=liveness['slot']:raise ValueError('Input precheck missing or slot changed')
        until=time.monotonic()+5;quiet=None
        while time.monotonic()<until:
            now=time.monotonic()
            if source()==NEUTRAL:
                if quiet is None:quiet=now
                if now-quiet>=.5:break
            else:quiet=None
            time.sleep(.01)
        else:raise ValueError('Release controls before discovery')
        selection=json.loads((PRIVATE/'rollback-selection.json').read_text());saved=json.loads((pathlib.Path(selection['root'])/'work/private/bridge-session.json').read_text(encoding='utf-8-sig'))
        spec=importlib.util.spec_from_file_location('accepted_switch_discovery',WORK/'bridge-switch-live.py');discovery=importlib.util.module_from_spec(spec);spec.loader.exec_module(discovery)
        publish('DISCOVERING');ip=discovery.discover(int(saved['session'],16),plan['discovery_seconds'])
        def input_source():
            nonlocal reads
            value=source();reads+=1;return value
        from phase_gap_probe_v2 import GapObservedClient
        client=GapObservedClient(Client(ip,int(saved['session'],16),input_source=input_source))
        def collect():
            try:collect_frames(client,inbox.put_nowait,stop.is_set,pause=client.pause)
            except BaseException as exc:
                try:inbox.put_nowait(exc)
                except queue.Full:stop.set()
        def stop_output():
            result={};owner.stop(reader,result);return result
        from written_pcm_probe import WrittenPCMProbe
        pcm=WrittenPCMProbe(reader.stream,frame_limit=1900)
        game=GameSession(lambda:reader.mode(b'\x01\x12\x02\x40\x00'),lambda l,r:pcm.send(safe.waveform(l,r,maximum_offset=12)),stop_output)
        thread=threading.Thread(target=collect,daemon=True);thread.start();timer=TimerResolution()
        if not timer.start():raise RuntimeError('Timer acquisition failed')
        until=time.perf_counter()+5
        while not game.output.renderer.upstream:
            if cancelled():raise RuntimeError('Cancelled before upstream')
            f=inbox.get(timeout=max(.001,until-time.perf_counter()))
            if isinstance(f,BaseException):raise f
            f['processed_at']=time.perf_counter();game.feed(f)
        started=time.perf_counter();ready=time.monotonic();deadline=ready+120;last_ui=0.;phase_name='INPUT_READY'
        report['live_started_at_pc_clock']=started
        while time.perf_counter()-started<plan['host_seconds']:
            if cancelled():game.fail('Game cancelled');raise RuntimeError('Game cancelled')
            while not inbox.empty():
                f=inbox.get_nowait()
                if isinstance(f,BaseException):raise f
                f['processed_at']=time.perf_counter();game.feed(f)
            if stop.is_set():raise RuntimeError('Collector stopped unexpectedly')
            if game.output.fault and not fault_observed:
                if game.output.dirty or game.output.cleanup_error:
                    raise RuntimeError('Output fault without confirmed stop; ending session immediately')
                fault_observed=True
                report['transport_at_output_fault']=client.snapshot()
                report['output_at_fault']=dict(frames=game.output.frames,active_ms=list(game.output.renderer.active_total),stop_confirmed=game.output.summary()['output_stop_confirmed'])
                phase_name='MUTED_FAULT';publish('MUTED_FAULT',deadline_monotonic=deadline)
            if phase_name=='INPUT_READY':
                now=time.monotonic()
                if now-last_ui>=.2:
                    publish('INPUT_READY',deadline_monotonic=deadline,source_neutral_ready=game.source_ready());last_ui=now
                if arm.exists():
                    requested=json.loads(arm.read_text())['requested_at_monotonic']
                    if type(requested) not in (int,float) or not ready<=requested<=ready+plan['arm_latest_seconds'] or not 0<=now-requested<2:raise ValueError('Stale or late game click')
                    game.arm(source()==NEUTRAL,time.perf_counter()-started);phase_name='ARMED';publish('ARMED',deadline_monotonic=deadline)
            game.tick()
            if game.output.stopped_at is not None and counts_at_stop is None:
                counts_at_stop=(reads,source.nonneutral_reads)
                phase_name='MUTED_FAULT' if game.output.fault else 'MUTED';publish(phase_name,deadline_monotonic=deadline)
            if game.terminal:break
            time.sleep(.001)
        if not game.terminal:raise TimeoutError('Game terminal handshake incomplete')
        thread.join(1)
        report.update(terminal_received=client.terminal_received,terminal_ack_replied=client.terminal_ack_replied,collector_ended=not thread.is_alive())
    except BaseException as exc:report['error']=repr(exc)
    finally:
        errors=[]
        if 'started' in locals():report['live_elapsed_seconds']=time.perf_counter()-started
        def finalize(label,action):
            try:action()
            except BaseException as exc:errors.append(label+': '+repr(exc))
        if game:
            finalize('output stop',game.output.stop);report.update(game.summary())
        if pcm:finalize('PCM summary',lambda:report.update(written_pcm=pcm.snapshot()))
        stop.set()
        if thread:finalize('collector join',lambda:thread.join(1))
        if client:
            report['transport_diagnostics']=client.snapshot()
            finalize('transport close',client.close)
        if source:
            after=counts_at_stop or (reads,source.nonneutral_reads)
            report['input_relay']=dict(slot=source.slot,reads_after_output_stop=reads-after[0],nonneutral_reads_after_output_stop=source.nonneutral_reads-after[1],
                last_pro_input=source.previous.hex() if source.previous is not None else None,last_read_at_pc_clock=getattr(source,'last_read_at',None),last_nonneutral_at_pc_clock=getattr(source,'last_nonneutral_at',None))
        if reader:finalize('reader close',reader.close)
        if 'safe' in locals():finalize('HID exit',safe.ro.lib.hid_exit)
        if timer:finalize('timer release',timer.close)
        report['timer_released']=timer is None or not timer.active;report['finalization_errors']=errors
        candidate=dict(report,status='PASSED_SWITCH_FIDELITY_CHILD_PENDING_FLASH_LOG')
        if game_child_passed(candidate):report=candidate
        finalize('phase close',lambda:publish('ENDED'));result_path.write_text(json.dumps(report,indent=2))
    return 0 if game_child_passed(report) else 1

def play(plan_path,picotool):
    plan=json.loads(plan_path.read_text());validate_game_plan(plan)
    if sys.platform!='win32':raise RuntimeError('Windows adapters required')
    from bridge_windows import load_owner
    from bridge_process import communicate_bounded
    from v043_installation import verify_installed
    from v043_game_gate import authorize
    from listener_readiness import wait_for_discovery
    stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S');paths={n:PRIVATE/('fidelity-game-'+n+'-'+stamp+'.json') for n in ('backup','child','phase','arm','liveness')}
    record_path=pathlib.Path(json.loads((PRIVATE/'v043-install-selection.json').read_text())['record']);record=json.loads(record_path.read_text())
    report=dict(status='INCOMPLETE',plan_sha256=digest(plan_path),actual_switch_game=True,host_flash_write=False,firmware_log_write_expected=True,persistent_flydigi_commands=0,flash_log_validation_pending=True)
    owner=load_owner();safe=owner.safe;reader=backup=proc=ui=None;dirty=False
    try:
        report['firmware_preflight']=verify_installed(record_path,picotool,record['pico_serial'])
        f=report['firmware_preflight']
        if f['baseline_generation']!=plan['expected_flash_generation'] or f['installed_snapshot_sha256']!=plan['expected_full_flash_sha256']:raise ValueError('Game baseline differs from the explicit plan')
        accepted=authorize(ROOT/'docs/V043_STAGED_GAME_PREREQUISITE_20261023.json',f)
        report['accepted_input_proof']={k:accepted[k] for k in ('verified','firmware_sha256','accepted_input_generation','source_hashes')}
        hotspot=json.loads(subprocess.check_output(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(ROOT/'tools/read_hotspot_state.ps1')],text=True));report['hotspot_preflight']=hotspot
        if hotspot.get('hotspot_state')!='On' or hotspot.get('band')!='TwoPointFourGigahertz' or hotspot.get('iphone_usb_source') is not True:raise ValueError('Original iPhone USB / 2.4GHz hotspot required')
        from game_input_liveness import passed as liveness_passed
        print('PC_INPUT_LIVENESS_REQUIRED; Pico stays on PC; follow the read-only window',flush=True)
        check=subprocess.Popen([sys.executable,str(ROOT/'tools/game_input_liveness.py'),str(paths['liveness'])],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
        _,check_error,check_killed=communicate_bounded(check,55)
        report['pc_input_liveness']=json.loads(paths['liveness'].read_text()) if paths['liveness'].exists() else {}
        if check_killed or check.returncode!=0 or not liveness_passed(report['pc_input_liveness']):raise ValueError('Actual PC button press/release precheck failed; do not move Pico')
        reader=safe.open_reader({});backup=owner.backup(reader,paths['backup']);reader.close();reader=None
        ui=subprocess.Popen([sys.executable,str(ROOT/'tools/fidelity_game_window.py'),str(paths['arm']),str(paths['phase'])],creationflags=subprocess.CREATE_NO_WINDOW)
        proc=subprocess.Popen([sys.executable,str(pathlib.Path(__file__).absolute()),'--child',str(plan_path),*[str(paths[k]) for k in ('backup','child','phase','arm')]],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,creationflags=subprocess.CREATE_NO_WINDOW);dirty=True
        began=time.monotonic();wait_for_discovery(proc,paths['phase']);report['post_neutral_discovery_ready']=True
        (PRIVATE/'fidelity-game-listener-ready.json').write_text(json.dumps(dict(stamp=stamp,post_neutral_discovery_ready=True,child_pid=proc.pid)))
        print('FIDELITY_GAME_DISCOVERY_READY; await explicit USB-swap instruction; output remains muted until manual click',flush=True)
        _,stderr,killed=communicate_bounded(proc,max(.001,plan['guardian_seconds']-(time.monotonic()-began)));report.update(child_exit=proc.returncode,guardian_killed_child=killed,child_stderr=stderr[-1500:])
        if paths['child'].exists():report['child']=json.loads(paths['child'].read_text())
        reader=safe.open_reader({});owner.identity(reader,backup);owner.stop(reader,report);dirty=False;owner.verify(reader,backup,report)
        if game_parent_passed(report,plan):report['status']='PASSED_SWITCH_FIDELITY_PROGRAM_PENDING_FLASH_LOG'
    except BaseException as exc:report['error']=repr(exc).replace(record['pico_serial'],'[private board]')
    finally:
        errors=[]
        def finalize(label,action):
            try:action()
            except BaseException as exc:errors.append(label+': '+repr(exc).replace(record['pico_serial'],'[private board]'))
        if proc and proc.poll() is None:
            finalize('kill child',proc.kill);finalize('reap child',lambda:proc.wait(2))
        if backup and dirty:
            try:
                if reader is None:reader=safe.open_reader({})
                owner.identity(reader,backup);owner.stop(reader,report);owner.verify(reader,backup,report)
            except BaseException as exc:errors.append('stop/verify: '+repr(exc))
        if reader:finalize('close reader',reader.close)
        if ui and ui.poll() is None:
            finalize('close window',ui.terminate);finalize('reap window',lambda:ui.wait(2))
        finalize('HID exit',safe.ro.lib.hid_exit)
        if errors:report['cleanup_error']='; '.join(errors);report['status']='INCOMPLETE'
        out=ROOT/'docs'/('FIDELITY_GAME_RUN_'+stamp+'.json');out.write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k!='child'},indent=2));print(out)
    return 0 if report['status']=='PASSED_SWITCH_FIDELITY_PROGRAM_PENDING_FLASH_LOG' else 1

def main():
    p=argparse.ArgumentParser(description=__doc__);g=p.add_mutually_exclusive_group(required=True);g.add_argument('--prepare',type=pathlib.Path);g.add_argument('--play',type=pathlib.Path);g.add_argument('--child',nargs=5,type=pathlib.Path);p.add_argument('--picotool',type=pathlib.Path);a=p.parse_args()
    if a.prepare:
        plan=build_game_plan()
        with a.prepare.open('x') as f:json.dump(plan,f,indent=2)
        print(a.prepare);return 0
    if a.child:return child(*a.child)
    if not a.picotool:p.error('--play requires explicit picotool')
    return play(a.play,a.picotool)

if __name__=='__main__':raise SystemExit(main())
