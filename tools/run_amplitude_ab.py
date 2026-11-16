"""Prepare offline by default command, or explicitly play one guarded PC-only A/B."""
import argparse,datetime,json,pathlib,subprocess,sys,time
from amplitude_ab_plan import ROOT,build_plan,validate_plan,play_segment,ab_child_succeeded,digest
WORK=ROOT/'handoff/2026-10-22/work';PRIVATE=WORK/'private'
sys.path.insert(0,str(WORK))

def child(plan_path,backup_path,report_path,phase,arm):
    report=dict(status='INCOMPLETE',segments=[],persistent_flydigi_commands=0);reader=None;timer=None
    def publish(state,**fields):phase.write_text(json.dumps(dict(phase=state,clock='monotonic',**fields)),encoding='utf-8')
    def cancelled():return arm.with_suffix('.cancel').exists()
    def wait(seconds):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            if cancelled():raise RuntimeError('Comparison cancelled')
            time.sleep(min(.05,max(0,end-time.monotonic())))
    try:
        plan=json.loads(plan_path.read_text(encoding='utf-8'));validate_plan(plan)
        from bridge_windows import load_owner,TimerResolution,XInputSource
        from bridge_input import NEUTRAL
        owner=load_owner();safe=owner.safe;b=json.loads(backup_path.read_text(encoding='utf-8'))
        reader=safe.open_reader({});owner.identity(reader,b);before={};owner.verify(reader,b,before)
        if not before['configuration_unchanged']:raise ValueError('Configuration changed before A/B')
        source=XInputSource();until=time.monotonic()+5;neutral_since=None
        while time.monotonic()<until:
            now=time.monotonic()
            if source()==NEUTRAL:
                if neutral_since is None:neutral_since=now
                if now-neutral_since>=.5:break
            else:neutral_since=None
            time.sleep(.01)
        else:raise ValueError('Release controls and center sticks before A/B')
        ready=time.monotonic();deadline=ready+45;publish('READY',deadline_monotonic=deadline)
        while not arm.exists() and time.monotonic()<deadline:
            if cancelled():raise RuntimeError('Comparison cancelled before manual click')
            time.sleep(.05)
        if cancelled():raise RuntimeError('Comparison cancelled')
        if not arm.exists():raise TimeoutError('No manual click; no output started')
        requested=json.loads(arm.read_text(encoding='utf-8'))['requested_at_monotonic'];now=time.monotonic()
        if type(requested) not in (int,float) or not ready<=requested<=deadline or not 0<=now-requested<2:raise ValueError('Stale or invalid manual click')
        report.update(manual_armed=True,manual_accepted_at_monotonic=time.monotonic());publish('PREPARE');wait(6)
        timer=TimerResolution()
        if not timer.start():raise RuntimeError('Required Windows timer unavailable')
        reader.allowed_modes=owner.MODES;reader.maximum_offset=12
        for segment in plan['segments']:
            if source()!=NEUTRAL:raise ValueError('Controls must remain released for A/B')
            entry=dict(label=segment['label'],stop={});publish(segment['label']);report['segments'].append(entry)
            def stop():
                owner.stop(reader,entry['stop']);entry['stop']['confirmed_at_monotonic']=time.monotonic()
            def enable():
                reader.mode(b'\x01\x12\x02\x40\x00');entry['started_at_monotonic']=time.monotonic()
            entry['playback']=play_segment(segment,enable,
                lambda left,right:reader.stream(safe.waveform(left,right,maximum_offset=12)),stop,cancelled=cancelled)
            if segment['label']=='A':publish('GAP');wait(5)
        report['status']='PASSED_FIDELITY_AB_CLIP_PROGRAM'
    except BaseException as exc:report['error']=repr(exc)
    finally:
        if reader:reader.close()
        if 'safe' in locals():safe.ro.lib.hid_exit()
        if timer:timer.close()
        report['timer_released']=timer is None or not timer.active
        publish('ENDED');report_path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    return 0 if report['status']=='PASSED_FIDELITY_AB_CLIP_PROGRAM' else 1

def play(plan_path):
    plan=json.loads(plan_path.read_text(encoding='utf-8'));validate_plan(plan)
    if sys.platform!='win32':raise RuntimeError('Windows hardware adapter required')
    from bridge_windows import load_owner
    from bridge_process import communicate_bounded
    owner=load_owner();safe=owner.safe;stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    paths={name:PRIVATE/('amplitude-ab-'+name+'-'+stamp+'.json') for name in ('backup','child','phase','arm')}
    report=dict(status='INCOMPLETE',plan_sha256=digest(plan_path),pico_access=False,switch_access=False,persistent_flydigi_commands=0,automatic_resume=False)
    reader=backup=proc=ui=None;dirty=False
    try:
        reader=safe.open_reader(report);backup=owner.backup(reader,paths['backup']);reader.close();reader=None
        ui=subprocess.Popen([sys.executable,str(ROOT/'tools/amplitude_ab_window.py'),str(paths['arm']),str(paths['phase'])],creationflags=subprocess.CREATE_NO_WINDOW)
        proc=subprocess.Popen([sys.executable,str(pathlib.Path(__file__).absolute()),'--child',str(plan_path),str(paths['backup']),str(paths['child']),str(paths['phase']),str(paths['arm'])],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,creationflags=subprocess.CREATE_NO_WINDOW);dirty=True
        _,stderr,killed=communicate_bounded(proc,75)
        report.update(child_exit=proc.returncode,guardian_killed_child=killed,child_stderr=stderr[-1500:])
        if paths['child'].exists():report['child']=json.loads(paths['child'].read_text(encoding='utf-8'))
        reader=safe.open_reader({});owner.identity(reader,backup);owner.stop(reader,report);dirty=False;owner.verify(reader,backup,report)
        if ab_child_succeeded(report.get('child'),proc.returncode,plan,killed) and report['runtime_disable_ack'] and report['configuration_unchanged']:report['status']='PASSED_FIDELITY_AB_PROGRAM_AND_CONFIG'
    except BaseException as exc:report['error']=repr(exc)
    finally:
        if proc and proc.poll() is None:proc.kill();proc.wait(timeout=2)
        if backup and dirty:
            try:
                if reader is None:reader=safe.open_reader({})
                owner.identity(reader,backup);owner.stop(reader,report);owner.verify(reader,backup,report)
            except BaseException as exc:report['cleanup_error']=repr(exc)
        if reader:reader.close()
        if ui and ui.poll() is None:ui.terminate();ui.wait(timeout=2)
        safe.ro.lib.hid_exit()
        output=ROOT/'docs'/('AMPLITUDE_AB_RUN_'+stamp+'.json');output.write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps({k:v for k,v in report.items() if k!='child'},indent=2));print(output)
    return 0 if report['status']=='PASSED_FIDELITY_AB_PROGRAM_AND_CONFIG' else 1

def main():
    p=argparse.ArgumentParser(description=__doc__);group=p.add_mutually_exclusive_group(required=True)
    group.add_argument('--prepare',type=pathlib.Path);group.add_argument('--play',type=pathlib.Path)
    group.add_argument('--child',nargs=5,type=pathlib.Path)
    a=p.parse_args()
    if a.prepare:
        plan=build_plan()
        with a.prepare.open('x',encoding='utf-8') as out:json.dump(plan,out,indent=2)
        print(json.dumps({k:v for k,v in plan.items() if k!='segments'},indent=2));return 0
    if a.child:return child(*a.child)
    return play(a.play)

if __name__=='__main__':raise SystemExit(main())
