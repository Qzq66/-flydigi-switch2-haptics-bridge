"""Three bounded calibration pulses, independent parent cleanup, no saved settings.

This deliberately extends prompt duration; it is not faithful Switch replay.
"""
import pathlib,importlib.util,json,time,math,datetime,subprocess,sys,ctypes as C,argparse
HERE=pathlib.Path(__file__).absolute().parent
sp=importlib.util.spec_from_file_location('owner',HERE/'flydigi-owner-hotplug.py')
owner=importlib.util.module_from_spec(sp);sp.loader.exec_module(owner)
safe=owner.safe;OUT=owner.OUT

def schedule(level):
    # Isolate duration first, then only if needed test amplitude at fixed 320ms.
    plans={'duration':[(40,3),(120,3),(320,3)],'confirm120':[(120,3)]*3,'amplitude':[(320,3),(320,4),(320,5)],'single':[(120,3),(120,5),(120,5)],'stronger':[(120,5),(120,8),(120,12)]}
    settings=plans[level]
    if level=='single':
        blocks=[]
        for at in range(-2000,6184,8):
            pair=[[128]*8,[128]*8]
            for n,(duration,amplitude) in enumerate(settings):
                side=0 if n<2 else 1;frequency=160 if side==0 else 320;relative=at-n*3000
                for i in range(8):
                    if 0<=relative+i<duration:pair[side][i]=128+round(amplitude*math.sin(2*math.pi*frequency*(relative+i)/1000))
            safe.waveform(*pair);blocks.append((at/1000,*pair))
        return settings,blocks
    blocks=[]
    for n,(duration,amplitude) in enumerate(settings):
        start=n*3000
        for at in range(start,start+duration,8):
            pair=[]
            for frequency in (160,320):
                pair.append([128+round(amplitude*math.sin(2*math.pi*frequency*(at-start+i)/1000)) if at-start+i<duration else 128 for i in range(8)])
            blocks.append((at/1000,pair[0],pair[1]))
        # Continue neutral frames for 64ms after each pulse, then wait silently.
        for at in range(start+duration,start+duration+64,8):blocks.append((at/1000,[128]*8,[128]*8))
    for _,left,right in blocks:safe.waveform(left,right,maximum_offset=12 if level=='stronger' else 5)
    return settings,blocks

def child(bp,cp,level):
    b=json.loads(bp.read_text(encoding='utf-8'));settings,blocks=schedule(level)
    report=dict(status='INCOMPLETE',settings=settings,frames=0,pulse_started=[],maximum_offset=0)
    if level=='single':report.update(pulse_sides=['left','left','right'],continuous_neutral_background=True)
    r=None;dirty=False;timer=False
    try:
        r=safe.open_reader({});owner.identity(r,b)
        motor,_=safe.read_ram(r,6)
        if motor.hex()!=b['ram']['motors']['raw_hex'] or list(r.state())!=b['state_before']:raise ValueError('Configuration changed before output')
        r.allowed_modes=owner.MODES;r.maximum_offset=12 if level=='stronger' else 5;timer=C.WinDLL('winmm').timeBeginPeriod(1)==0
        dirty=True;r.mode(b'\x01\x12\x02\x40\x00');start=time.perf_counter()+(6 if level in ('single','stronger') else 2)
        max_late=0
        for relative,left,right in blocks:
            target=start+relative;now=time.perf_counter()
            if now<target:time.sleep(target-now)
            late=time.perf_counter()-target;max_late=max(max_late,late)
            if late>.016:raise TimeoutError('Calibration scheduling late; stopped without catch-up')
            if relative in (0,3,6):report['pulse_started'].append(relative)
            r.stream(safe.waveform(left,right,maximum_offset=r.maximum_offset));report['frames']+=1
            report['maximum_offset']=max(report['maximum_offset'],max(abs(v-128) for v in left+right))
        report.update(status='THREE_PULSES_SENT',maximum_schedule_lateness_ms=max_late*1000)
    except BaseException as e:report['error']=repr(e)
    finally:
        if r and dirty:
            try:owner.stop(r,report)
            except BaseException as e:report['cleanup_error']=repr(e)
        if r:r.close()
        safe.ro.lib.hid_exit()
        if timer:C.WinDLL('winmm').timeEndPeriod(1)
        cp.write_text(json.dumps(report,indent=2),encoding='utf-8')
    return 0 if report['status']=='THREE_PULSES_SENT' and report.get('runtime_disable_ack') else 1

def main(level):
    stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    bp=OUT/f'flydigi-calibration-{level}-backup-{stamp}.json';cp=OUT/f'flydigi-calibration-{level}-child-{stamp}.json'
    settings,_=schedule(level);report=dict(status='INCOMPLETE',calibration=level,pulse_settings_ms_and_offset=settings,
        persistent_write_commands=0,independent_parent_guardian=True,automatic_resume=False,
        path='PC direct to Flydigi; deliberate duration/amplitude calibration, not Switch replay')
    r=None;b=None;proc=None;dirty=False
    try:
        r=safe.open_reader(report);b=owner.backup(r,bp);r.close();r=None
        dirty=True
        proc=subprocess.Popen([sys.executable,str(pathlib.Path(__file__).absolute()),'--child',str(bp),str(cp),level],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
        try:stdout,stderr=proc.communicate(timeout=18 if level in ('single','stronger') else 14)
        except subprocess.TimeoutExpired:
            proc.kill();stdout,stderr=proc.communicate(timeout=2);report['guardian_killed_late_child']=True
        report['child_exit']=proc.returncode;report['child_error']=stderr[-1500:]
        if cp.exists():report['child']=json.loads(cp.read_text(encoding='utf-8'))
        r=safe.open_reader(report);owner.identity(r,b);owner.stop(r,report);dirty=False;owner.verify(r,b,report)
        if proc.returncode==0 and report['configuration_unchanged'] and report['runtime_disable_ack']:report['status']='PASSED_OUTPUT_STOP_AND_CONFIG_RECHECK'
    except BaseException as e:report['error']=repr(e)
    finally:
        if proc and proc.poll() is None:proc.kill();proc.wait(timeout=2)
        if b and dirty:
            try:
                if r is None:r=safe.open_reader(report)
                owner.identity(r,b);owner.stop(r,report);owner.verify(r,b,report)
            except BaseException as e:report['cleanup_error']=repr(e)
        if r:r.close()
        safe.ro.lib.hid_exit()
        path=OUT/f'flydigi-calibration-{level}-{stamp}.json';path.write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report,indent=2));print(str(path))
    return 0 if report['status']=='PASSED_OUTPUT_STOP_AND_CONFIG_RECHECK' else 1

if __name__=='__main__':
    if len(sys.argv)==5 and sys.argv[1]=='--child':raise SystemExit(child(pathlib.Path(sys.argv[2]),pathlib.Path(sys.argv[3]),sys.argv[4]))
    p=argparse.ArgumentParser();p.add_argument('--level',choices=('duration','confirm120','amplitude','single','stronger'),default='duration');a=p.parse_args();raise SystemExit(main(a.level))
