"""One bounded captured-fragment replay, with separate parent cleanup guardian.

Uses proven read/backup, volatile group mode and <=5 sample-code output only.
No save, reset, profile selection, per-grip mode or firmware commands.
"""
import pathlib,importlib.util,json,hashlib,time,subprocess,sys,ctypes as C,datetime
HERE=pathlib.Path(__file__).absolute().parent
spec=importlib.util.spec_from_file_location('owner',HERE/'flydigi-owner-hotplug.py')
owner=importlib.util.module_from_spec(spec);spec.loader.exec_module(owner)
safe=owner.safe;OUT=owner.OUT

def load_plan():
    path=OUT/'switch2-captured-replay-plan.json'
    proof=json.loads((OUT/'switch2-captured-replay-plan-proof.json').read_text(encoding='utf-8'))
    if hashlib.sha256(path.read_bytes()).hexdigest()!=proof['plan_sha256']:raise ValueError('Plan changed')
    plan=json.loads(path.read_text(encoding='utf-8'));blocks=plan['blocks']
    if plan['sample_rate']!=1000 or plan['frame_period_ms']!=8 or not 1<=len(blocks)<=32 or plan['duration_ms']!=len(blocks)*8:raise ValueError('Plan bounds')
    for b in blocks:safe.waveform(b['left'],b['right'])
    if any(v!=128 for b in blocks[-8:] for side in ('left','right') for v in b[side]):raise ValueError('Neutral tail missing')
    return plan

def child(backup_path):
    plan=load_plan();b=json.loads(backup_path.read_text(encoding='utf-8'))
    r=None;dirty=False;timer=False;report={'frames':0,'timings_ms':[]}
    try:
        r=safe.open_reader({});owner.identity(r,b)
        motor,_=safe.read_ram(r,6)
        if motor.hex()!=b['ram']['motors']['raw_hex']:raise ValueError('Motor RAM changed')
        r.allowed_modes=owner.MODES
        timer=C.WinDLL('winmm').timeBeginPeriod(1)==0
        dirty=True;r.mode(b'\x01\x12\x02\x40\x00')
        start=time.perf_counter()
        for i,block in enumerate(plan['blocks']):
            target=start+i*.008;now=time.perf_counter()
            if now-target>.04 or now-start>.4:raise TimeoutError('Schedule late; stop without burst catch-up')
            if now<target:time.sleep(target-now)
            report['timings_ms'].append(round((time.perf_counter()-start)*1000,3))
            r.stream(safe.waveform(block['left'],block['right']));report['frames']+=1
        report['status']='PLAYBACK_SENT'
    finally:
        if r and dirty:owner.stop(r,report)
        if r:r.close()
        safe.ro.lib.hid_exit()
        if timer:C.WinDLL('winmm').timeEndPeriod(1)
        (OUT/'flydigi-captured-replay-child.json').write_text(json.dumps(report,indent=2),encoding='utf-8')

def main():
    plan=load_plan();stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    bp=OUT/f'flydigi-captured-replay-backup-{stamp}.json'
    report=dict(status='INCOMPLETE',persistent_write_commands=0,nominal_ms=plan['duration_ms'],
        hardware_path='PC offline file to Flydigi only; no Pico or Switch realtime transport',
        maximum_sample_offset=5,cleanup_guardian='parent process',automatic_resume=False)
    r=None;proc=None;b=None;dirty=False
    try:
        r=safe.open_reader(report);b=owner.backup(r,bp);report['backup_file']=bp.name
        r.close();r=None
        print('Backup verified; starting one very short low-amplitude left/right replay in 2 seconds.',flush=True)
        time.sleep(2)
        dirty=True
        proc=subprocess.Popen([sys.executable,str(pathlib.Path(__file__).absolute()),'--child',str(bp)],
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
        try:stdout,stderr=proc.communicate(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill();stdout,stderr=proc.communicate(timeout=2);report['guardian_killed_late_owner']=True
        report['child_exit']=proc.returncode;report['child_error']=stderr[-1500:]
        r=safe.open_reader(report);owner.identity(r,b);owner.stop(r,report);dirty=False
        owner.verify(r,b,report)
        if proc.returncode==0 and report.get('configuration_unchanged') and report.get('runtime_disable_ack'):
            report['status']='PASSED_BOUNDED_REPLAY_STOP_AND_CONFIG_RECHECK'
    except BaseException as e:report['error']=repr(e)
    finally:
        if proc and proc.poll() is None:proc.kill();proc.wait(timeout=2)
        if dirty and b:
            try:
                if r is None:r=safe.open_reader(report)
                owner.identity(r,b);owner.stop(r,report)
            except BaseException as e:report['cleanup_error']=repr(e)
        if b and r and not report.get('configuration_unchanged'):
            try:owner.verify(r,b,report)
            except BaseException as e:report['recheck_error']=repr(e)
        if r:r.close()
        safe.ro.lib.hid_exit()
        out=OUT/f'flydigi-captured-replay-{stamp}.json'
        out.write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2));print(str(out))
    return 0 if report['status']=='PASSED_BOUNDED_REPLAY_STOP_AND_CONFIG_RECHECK' else 1

if __name__=='__main__':
    if len(sys.argv)==3 and sys.argv[1]=='--child':child(pathlib.Path(sys.argv[2]))
    else:raise SystemExit(main())
