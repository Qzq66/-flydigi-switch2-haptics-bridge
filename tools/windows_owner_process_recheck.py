"""Bounded physical owner/timer/process diagnostics, not a Switch live test."""
import argparse,datetime,json,math,pathlib,subprocess,sys,time
ROOT=pathlib.Path(__file__).absolute().parents[1]
WORK=ROOT/'handoff/2026-10-22/work';sys.path.insert(0,str(WORK))
from bridge_windows import load_owner,TimerResolution
from bridge_process import communicate_bounded

def child(case,bp,ready,rp):
    owner=load_owner();safe=owner.safe;b=json.loads(bp.read_text(encoding='utf-8'))
    report={'case':case,'status':'INCOMPLETE','frames':0};r=None;dirty=False;timer=TimerResolution()
    try:
        r=safe.open_reader({});owner.identity(r,b);owner.verify(r,b,report)
        if not report['configuration_unchanged']:raise ValueError('Configuration differs before output')
        r.allowed_modes=owner.MODES;r.maximum_offset=12
        if not timer.start():raise RuntimeError('Timer acquisition failed')
        dirty=True;r.mode(b'\x01\x12\x02\x40\x00');start=time.perf_counter()
        for block in range(15):
            target=start+block*.008;now=time.perf_counter()
            if now>target+.016:raise RuntimeError('Scheduler late; refusing catch-up')
            if target>now:time.sleep(target-now)
            sides=[[128+round(12*math.sin(2*math.pi*hz*(block*8+i)/1000)) for i in range(8)] for hz in (160,320)]
            r.stream(safe.waveform(*sides,maximum_offset=12));report['frames']+=1
            if block==0:ready.write_text('first_frame_sent',encoding='utf-8')
            if case=='exception' and block==5:raise RuntimeError('deliberate diagnostic exception')
        time.sleep(max(0,start+.120-time.perf_counter()))
        if case=='timeout':raise RuntimeError('Guardian failed to interrupt bounded pulse')
        report['status']='NORMAL_RETURN'
    except BaseException as exc:report['error']=repr(exc)
    finally:
        if r and dirty:
            try:owner.stop(r,report)
            except BaseException as exc:report['cleanup_error']=repr(exc)
        if r:r.close()
        safe.ro.lib.hid_exit();timer.close();report['timer_released']=not timer.active
        rp.write_text(json.dumps(report,indent=2),encoding='utf-8')
    return 0 if report['status']=='NORMAL_RETURN' else 1

def main():
    owner=load_owner();safe=owner.safe;private=WORK/'private';private.mkdir(exist_ok=True)
    stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S');cases=[]
    try:
        for case in ('normal','exception','timeout'):
            record={'case':case,'passed':False};cases.append(record)
            prefix=private/('owner-process-'+stamp+'-'+case)
            bp=prefix.with_suffix('.backup.json');rp=prefix.with_suffix('.child.json');ready=prefix.with_suffix('.ready')
            r=None;b=None;proc=None;dirty=False
            try:
                r=safe.open_reader({});b=owner.backup(r,bp);r.close();r=None
                print('PREPARING '+case,flush=True);time.sleep(6 if case=='normal' else 3)
                proc=subprocess.Popen([sys.executable,str(pathlib.Path(__file__).absolute()),'--child',case,str(bp),str(ready),str(rp)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
                dirty=True;until=time.perf_counter()+12
                while not ready.exists() and proc.poll() is None and time.perf_counter()<until:time.sleep(.002)
                if not ready.exists():raise RuntimeError('Child did not reach its first output frame')
                _,stderr,killed=communicate_bounded(proc,.035 if case=='timeout' else 3)
                stopped=time.perf_counter();record.update(killed=killed,exit_code=proc.returncode,stderr=stderr[-1000:])
                if rp.exists():record['child']=json.loads(rp.read_text(encoding='utf-8'))
                r=safe.open_reader({});owner.identity(r,b);owner.stop(r,record)
                record['parent_stop_after_child_exit_ms']=round((record['neutral_written_clock']-stopped)*1000,3)
                dirty=False;owner.verify(r,b,record)
                c=record.get('child',{})
                expected=(not killed and proc.returncode==0 and c.get('status')=='NORMAL_RETURN' and c.get('timer_released') and c.get('runtime_disable_ack')) if case=='normal' else ((not killed and proc.returncode!=0 and c.get('error')=="RuntimeError('deliberate diagnostic exception')" and c.get('runtime_disable_ack') and c.get('timer_released')) if case=='exception' else killed and proc.returncode!=0)
                record['passed']=bool(expected and not c.get('cleanup_error') and record['runtime_disable_ack'] and record['configuration_unchanged'])
            except BaseException as exc:record['error']=repr(exc)
            finally:
                if proc and proc.poll() is None:proc.kill();proc.wait(timeout=2)
                if b and dirty:
                    try:
                        if r is None:r=safe.open_reader({})
                        owner.identity(r,b);owner.stop(r,record);owner.verify(r,b,record)
                    except BaseException as exc:record['cleanup_error']=repr(exc)
                if r:r.close()
            print(json.dumps(record),flush=True)
            if not record['passed']:break
    finally:
        safe.ro.lib.hid_exit()
        passed=len(cases)==3 and all(c['passed'] for c in cases)
        report=dict(status='PASSED_PHYSICAL_OWNER_PROCESS_RECHECK' if passed else 'INCOMPLETE',cases=cases,persistent_write_commands=0,maximum_sample_offset=12,maximum_pulse_ms=120,automatic_resume=False,scope='Diagnostic controlled waves; no Switch, no network collector, no game validation. Forced child death cannot run its finally; parent independently disables output and rechecks all four RAM areas.')
        output=ROOT/'docs'/('WINDOWS_OWNER_PROCESS_RECHECK_'+stamp+'.json');output.write_text(json.dumps(report,indent=2),encoding='utf-8');print(str(output))
    return 0 if passed else 1

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--child',nargs=4);args=parser.parse_args()
    raise SystemExit(child(args.child[0],*[pathlib.Path(p) for p in args.child[1:]]) if args.child else main())
