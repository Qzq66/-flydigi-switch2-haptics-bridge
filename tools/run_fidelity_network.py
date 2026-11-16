"""Explicit SRAM-Pico/Wi-Fi replay entry; no hardware access with --prepare."""
import argparse,datetime,importlib.util,json,pathlib,queue,subprocess,sys,threading,time
from fidelity_network_session import ROOT,RAM_SHA,build_network_plan,validate_network_plan,digest,StreamSession,child_succeeded,program_succeeded
from fidelity_network_io import CapturedInjector,snapshot_then_reset,wait_full_flash
WORK=ROOT/'handoff/2026-10-22/work';PRIVATE=WORK/'private';sys.path.insert(0,str(WORK))
RAM=ROOT/'build/pico-v043-120s-ram-snapshot/pico_pro_capture.uf2'

def reset_probe(probe,snapshot_required=False):
    if not probe or not probe.m.handle or not probe.m.verified:raise ValueError('Cannot reset an unverified RAM Pico')
    if snapshot_required:
        evidence=snapshot_then_reset(lambda:probe.m.read_virtual(0x9280,8),lambda:probe.m.send(0x80,b'\xfeRESETLAB'))
    else:
        probe.m.send(0x80,b'\xfeRESETLAB');evidence=dict(pico_ram_reset_requested=True,snapshot_phase_confirmed=False)
    time.sleep(.35)
    return evidence

def child(plan_path,backup_path,output,phase,arm):
    report=dict(status='INCOMPLETE',manual_armed=False,events=[],persistent_flydigi_commands=0,flash_write=False,actual_switch_game=False)
    reader=probe=client=thread=session=injector=None;timer=None;end_requested=False;stop_collect=threading.Event();inbox=queue.Queue(maxsize=512)
    def publish(state,**fields):phase.write_text(json.dumps(dict(phase=state,clock='monotonic',**fields)))
    def cancelled():return arm.with_suffix('.cancel').exists()
    try:
        plan=json.loads(plan_path.read_text());validate_network_plan(plan)
        from bridge_windows import load_owner,TimerResolution,XInputSource
        from bridge_input import NEUTRAL
        from bridge_transport import Client
        from bridge_render import collect_frames
        from pico_v043_probe import Probe
        owner=load_owner();safe=owner.safe;b=json.loads(backup_path.read_text())
        reader=safe.open_reader({});owner.identity(reader,b);before={};owner.verify(reader,b,before)
        if not before['configuration_unchanged']:raise ValueError('Configuration changed before network replay')
        source=XInputSource();input_calls=0
        def input_source():
            nonlocal input_calls
            value=source();input_calls+=1;return value
        until=time.monotonic()+5;neutral_since=None
        while time.monotonic()<until:
            now=time.monotonic()
            if source()==NEUTRAL:
                if neutral_since is None:neutral_since=now
                if now-neutral_since>=.5:break
            else:neutral_since=None
            time.sleep(.01)
        else:raise ValueError('Release all controls before replay')
        probe=Probe();probe.open('ram');endpoint=probe.endpoint();m=probe.m
        selection=json.loads((PRIVATE/'rollback-selection.json').read_text());saved=json.loads((pathlib.Path(selection['root'])/'work/private/bridge-session.json').read_text(encoding='utf-8-sig'))
        if endpoint['session']!=int(saved['session'],16):raise ValueError('RAM endpoint session does not match current local network')
        m.send(0x80,b'\4');m.sub(3,b'\x30');m.sub(0x40,b'\2');m.sub(0x48,b'\1')
        client=Client(endpoint['ip'],endpoint['session'],input_source=input_source)
        def collect():
            try:collect_frames(client,inbox.put_nowait,stop_collect.is_set)
            except BaseException as exc:
                try:inbox.put_nowait(exc)
                except queue.Full:stop_collect.set()
        thread=threading.Thread(target=collect);thread.start();reader.allowed_modes=owner.MODES;reader.maximum_offset=12
        session=StreamSession(lambda:reader.mode(b'\x01\x12\x02\x40\x00'),lambda l,r:reader.stream(safe.waveform(l,r,maximum_offset=12)),lambda:stop_output())
        def stop_output():
            result={};owner.stop(reader,result);return result
        terminal=False;latest=None
        def consume():
            nonlocal terminal,latest
            while not inbox.empty():
                frame=inbox.get_nowait()
                if isinstance(frame,BaseException):raise frame
                frame['processed_at']=time.perf_counter();session.feed(frame);latest=frame
                if frame['flags']&16:terminal=True
            if stop_collect.is_set():raise RuntimeError('Collector stopped unexpectedly')
        def wait(seconds):
            end=time.monotonic()+seconds
            while time.monotonic()<end:
                if cancelled():raise RuntimeError('Replay cancelled')
                consume()
                if session.fault:raise RuntimeError(session.fault)
                time.sleep(.004)
        until=time.monotonic()+3
        while not (latest and latest['flags']&6==6):
            consume()
            if time.monotonic()>until:raise TimeoutError('No configured upstream heartbeat')
            time.sleep(.004)
        ready=time.monotonic();deadline=ready+45;publish('READY',deadline_monotonic=deadline)
        while not arm.exists() and time.monotonic()<deadline:wait(.02)
        if not arm.exists():raise TimeoutError('No manual click; no output started')
        requested=json.loads(arm.read_text())['requested_at_monotonic'];now=time.monotonic()
        if type(requested) not in (int,float) or not ready<=requested<=deadline or not 0<=now-requested<2:raise ValueError('Stale manual click')
        report['manual_armed']=True;publish('PREPARE');wait(6)
        if source()!=NEUTRAL:raise ValueError('Controls not released at replay start')
        timer=TimerResolution()
        if not timer.start():raise RuntimeError('Timer acquisition failed')
        consume();prefix=[e['motors'] for e in session.events];target=session.arm();armed_at=session.renderer.armed_at
        injector=CapturedInjector(plan['events'],armed_at+.100,lambda i,raw:m.send(0x10,bytes([i%16])+raw),plan['maximum_injection_lateness_seconds'])
        injector.start();output_lateness=[];output_write_seconds=[];calls_at_stop=None;updates_at_stop=None;safety_fields=[]
        publish('ACTIVE');runtime_end=time.perf_counter()+8
        while time.perf_counter()<runtime_end:
            if cancelled():session.abort(RuntimeError('Replay cancelled'))
            if injector.error and not session.fault:session.abort(RuntimeError(injector.error))
            consume();now=time.perf_counter()
            if not session.fault and session.dirty and now>=target:
                if now-target>plan['maximum_output_lateness_seconds']:
                    report['output_deadline_failure_seconds']=now-target;session.abort(RuntimeError('Output scheduler late; no catch-up'))
                else:
                    old=session.frames;session.tick(target);finished=time.perf_counter()
                    if session.frames>old:
                        output_lateness.append(now-target);output_write_seconds.append(finished-now)
                    target+=.008
            if (session.stopped_at is not None or session.fault) and calls_at_stop is None:
                session.stop()
                joined=injector.cancel_and_join() if session.fault else injector.join()
                report['injector_joined']=joined
                if not joined:raise RuntimeError('USB injector still running; no concurrent Pico read or reset permitted')
                calls_at_stop=input_calls;updates_at_stop=int.from_bytes(m.read_range(0x9238,4),'little');publish('MUTED')
            if calls_at_stop is not None and not end_requested and time.perf_counter()-session.stopped_at>=.25:
                report.update(input_calls_after_output_stop=input_calls-calls_at_stop,input_time_after_output_stop=source.last_read_at-session.stopped_at,
                    pico_input_updates_after_output_stop=int.from_bytes(m.read_range(0x9238,4),'little')-updates_at_stop)
                if session.fault:
                    m.send(0x10,b'\0'+bytes.fromhex('0001404000014040'));safety_fields.append('0001404000014040')
                m.send(0x80,b'\xfcENDLAB42');end_requested=True
            if terminal:break
            time.sleep(.001)
        if not terminal:raise TimeoutError('Terminal handshake did not complete')
        thread.join(timeout=1)
        report.update(injector.evidence());sent=report['sent_motor_fields']+safety_fields
        report.update(session.summary());report.update(sent_motor_fields=sent,initial_motor_fields=prefix,all_motor_fields_exact=[e['motors'] for e in session.events]==prefix+sent,
            sequence_contiguous=[e['sequence'] for e in session.events]==list(range(len(session.events))),output_lateness_seconds=output_lateness,output_write_seconds=output_write_seconds,
            terminal_received=client.terminal_received,terminal_ack_replied=client.terminal_ack_replied,collector_ended=not thread.is_alive())
        if session.fault or session.cleanup_error or not session.stops:raise RuntimeError('Output did not complete cleanly')
        if not report['injector_done'] or report['injector_error'] or len(sent)!=len(plan['events']) or not report['all_motor_fields_exact'] or not report['sequence_contiguous']:raise RuntimeError('Source/wire fields mismatch')
        if session.renderer.muted_reason!='single bilateral episode completed' or not all(100<=n<=320 for n in session.renderer.active_total):raise RuntimeError('One complete bilateral episode required')
        if not report['terminal_ack_replied'] or not report['collector_ended'] or report['input_calls_after_output_stop']<5 or report['input_time_after_output_stop']<.20 or report['pico_input_updates_after_output_stop']<=0:raise RuntimeError('Input/transport did not continue after output stop')
        report['status']='PASSED_RAM_WIFI_FIDELITY_REPLAY_CHILD'
    except BaseException as exc:report['error']=repr(exc)
    finally:
        finalization_errors=[]
        def finalize(label,action):
            try:action()
            except BaseException as exc:finalization_errors.append(label+': '+repr(exc))
        if session:
            finalize('stop output',session.stop)
            report.update(session.summary())
        usb_idle=True
        if injector:
            usb_idle=injector.cancel_and_join();report['injector_joined']=usb_idle
            # Keep any explicitly recorded safety neutral in the completed report.
            evidence=injector.evidence()
            if 'sent_motor_fields' in report:evidence.pop('sent_motor_fields')
            report.update(evidence)
            if not usb_idle:finalization_errors.append('USB injector did not join; parent guardian recovery required')
        stop_collect.set()
        if thread:finalize('join collector',lambda:thread.join(timeout=1))
        if client:finalize('close transport',client.close)
        if probe and usb_idle:
            try:report.update(reset_probe(probe,snapshot_required=end_requested))
            except BaseException as exc:report['pico_reset_error']=repr(exc)
            finalize('close Pico',probe.close)
        if reader:finalize('close Flydigi',reader.close)
        if 'safe' in locals():finalize('HID exit',safe.ro.lib.hid_exit)
        if timer:finalize('release timer',timer.close)
        report['timer_released']=timer is None or not timer.active
        report['finalization_errors']=finalization_errors
        publish('ENDED');output.write_text(json.dumps(report,indent=2))
    return 0 if 'plan' in locals() and child_succeeded(report,plan) else 1

def play(plan_path,picotool,nm):
    plan=json.loads(plan_path.read_text());validate_network_plan(plan)
    if sys.platform!='win32':raise RuntimeError('Windows hardware adapters required')
    from bridge_windows import load_owner
    from bridge_process import communicate_bounded
    from v043_installation import verify_installed
    record_path=pathlib.Path(json.loads((PRIVATE/'v043-install-selection.json').read_text())['record']);record=json.loads(record_path.read_text())
    if record['baseline_generation']!=plan['expected_flash_generation'] or record['installed_snapshot_sha256']!=plan['expected_full_flash_sha256']:raise ValueError('Installation record must match the explicit source-bound full Flash baseline')
    if digest(RAM)!=RAM_SHA:raise ValueError('Reviewed RAM image missing or changed')
    manifest=json.loads(RAM.with_suffix('.manifest.json').read_text())
    if manifest['profile']!='ram' or manifest['sha256']!=RAM_SHA or int(manifest['minimum_address'],16)<0x20000000 or int(manifest['maximum_end'],16)>0x20082000:raise ValueError('Invalid SRAM image bounds')
    symbols=subprocess.check_output([str(nm),'-S',str(RAM.with_suffix('.elf'))],text=True)
    if any(line.split()[-1] in ('flash_range_program','flash_range_erase') for line in symbols.splitlines() if line.split()):raise ValueError('RAM image must have no Flash mutation symbols')
    stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S');paths={name:PRIVATE/('fidelity-network-'+name+'-'+stamp+'.json') for name in ('backup','child','arm','phase')}
    console=PRIVATE/('fidelity-network-tools-'+stamp+'.txt');owner=load_owner();safe=owner.safe;reader=backup=proc=ui=None;dirty=False;loaded=False
    report=dict(status='INCOMPLETE',plan_sha256=digest(plan_path),flash_write=False,persistent_flydigi_commands=0,actual_switch_game=False,automatic_resume=False,ram_image_sha256=RAM_SHA)
    def command(args):
        with console.open('a') as out:
            r=subprocess.run([str(picotool),*map(str,args),'--ser',record['pico_serial']],stdout=out,stderr=subprocess.STDOUT,timeout=30,creationflags=subprocess.CREATE_NO_WINDOW)
        return r.returncode==0
    try:
        report['flash_before']=verify_installed(record_path,picotool,record['pico_serial'])
        hotspot=json.loads(subprocess.check_output(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(ROOT/'tools/read_hotspot_state.ps1')],text=True))
        report['hotspot_preflight']=hotspot
        if hotspot.get('hotspot_state')!='On' or hotspot.get('band')!='TwoPointFourGigahertz' or not hotspot.get('iphone_usb_source'):raise ValueError('Original iPhone USB / 2.4GHz hotspot required')
        reader=safe.open_reader(report);backup=owner.backup(reader,paths['backup']);reader.close();reader=None
        # Even a failed load command may have partially started the RAM image.
        loaded=True
        if not command(['load','-v','-x',RAM,'-t','uf2']):raise RuntimeError('SRAM-only load failed')
        dirty=True
        ui=subprocess.Popen([sys.executable,str(ROOT/'tools/fidelity_network_window.py'),str(paths['arm']),str(paths['phase'])],creationflags=subprocess.CREATE_NO_WINDOW)
        proc=subprocess.Popen([sys.executable,str(pathlib.Path(__file__).absolute()),'--child',str(plan_path),*[str(paths[k]) for k in ('backup','child','phase','arm')]],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
        _,stderr,killed=communicate_bounded(proc,140);report.update(child_exit=proc.returncode,guardian_killed_child=killed,child_stderr=stderr[-1500:])
        if paths['child'].exists():report['child']=json.loads(paths['child'].read_text())
        reader=safe.open_reader({});owner.identity(reader,backup);owner.stop(reader,report);dirty=False;owner.verify(reader,backup,report)
    except BaseException as exc:report['error']=repr(exc).replace(record['pico_serial'],'[private board]')
    finally:
        cleanup_errors=[]
        def finalize(label,action):
            try:action()
            except BaseException as exc:cleanup_errors.append(label+': '+repr(exc).replace(record['pico_serial'],'[private board]'))
        if proc and proc.poll() is None:
            finalize('kill child',proc.kill);finalize('reap child',lambda:proc.wait(timeout=2))
        if backup and dirty:
            try:
                if reader is None:reader=safe.open_reader({})
                owner.identity(reader,backup);owner.stop(reader,report);owner.verify(reader,backup,report)
            except BaseException as exc:report['cleanup_error']=repr(exc)
        if reader:finalize('close Flydigi',reader.close)
        if ui and ui.poll() is None:
            finalize('close window',ui.terminate);finalize('reap window',lambda:ui.wait(timeout=2))
        finalize('HID exit',safe.ro.lib.hid_exit)
        if loaded:
            try:
                # Child normally resets directly. On crash/kill, reset only a
                # uniquely identified initial or immutable-snapshot RAM043.
                verify=lambda:command(['verify',record['installed_snapshot'],'-t','bin','-o','0x10000000'])
                report['bootsel_wait_before_recovery']=wait_full_flash(verify,timeout=plan['bootsel_enumeration_wait_seconds'])
                if not report['bootsel_wait_before_recovery']['matched']:
                    from pico_v043_probe import Probe
                    p=Probe()
                    try:
                        try:p.open('ram')
                        except (ValueError,TimeoutError,AssertionError):
                            if not p.m.handle:raise
                            # Probe opened only the exact RAM043 USB identity.
                            # Initial BCAP is unavailable during the snapshot.
                            recovery=snapshot_then_reset(lambda:p.m.read_virtual(0x9280,8),lambda:p.m.send(0x80,b'\xfeRESETLAB',read_probe=True))
                            report['parent_snapshot_reset']=recovery;time.sleep(.35)
                        else:report['parent_initial_reset']=reset_probe(p)
                    finally:p.close()
                    report['bootsel_wait_after_recovery']=wait_full_flash(verify,timeout=plan['bootsel_enumeration_wait_seconds'])
                    if not report['bootsel_wait_after_recovery']['matched']:raise RuntimeError('Full Flash after RAM replay unverified; keep/reconnect BOOTSEL')
                report['full_flash_after_matches']=True
            except BaseException as exc:report['flash_cleanup_error']=repr(exc).replace(record['pico_serial'],'[private board]')
        if cleanup_errors:report['cleanup_error']='; '.join(cleanup_errors)+('; '+report['cleanup_error'] if report.get('cleanup_error') else '')
        if program_succeeded(report,plan):report['status']='PASSED_RAM_WIFI_FIDELITY_REPLAY_PROGRAM'
        out=ROOT/'docs'/('FIDELITY_NETWORK_RUN_'+stamp+'.json');out.write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k!='child'},indent=2));print(out)
    return 0 if report['status']=='PASSED_RAM_WIFI_FIDELITY_REPLAY_PROGRAM' else 1

def main():
    p=argparse.ArgumentParser(description=__doc__);g=p.add_mutually_exclusive_group(required=True);g.add_argument('--prepare',type=pathlib.Path);g.add_argument('--play',type=pathlib.Path);g.add_argument('--child',nargs=5,type=pathlib.Path)
    p.add_argument('--picotool',type=pathlib.Path);p.add_argument('--nm',type=pathlib.Path);p.add_argument('--baseline-report');a=p.parse_args()
    if a.prepare:
        plan=build_network_plan(a.baseline_report)
        with a.prepare.open('x') as out:json.dump(plan,out,indent=2)
        print(json.dumps({k:v for k,v in plan.items() if k!='events'},indent=2));return 0
    if a.child:return child(*a.child)
    if not a.picotool or not a.nm:p.error('--play requires explicit picotool and nm paths')
    return play(a.play,a.picotool,a.nm)

if __name__=='__main__':raise SystemExit(main())
