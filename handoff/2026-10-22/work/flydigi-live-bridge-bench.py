"""Actual Pico USB -> WiFi -> decoder -> bounded Flydigi bench, parent guarded.

Replays a verified prefix of captured Switch reports into RAM Pico only.
No persistent Flydigi commands. Does not claim an actual Switch live test.
"""
import pathlib,importlib.util,json,time,sys,subprocess,datetime,threading,queue,argparse
from bridge_runtime import Client,Renderer,BridgeFault
from bridge_process import communicate_bounded,child_succeeded
from bridge_windows import TimerResolution
HERE=pathlib.Path(__file__).absolute().parent
def module(name,file):
    spec=importlib.util.spec_from_file_location(name,HERE/file)
    obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj);return obj
owner=safe=OUT=probe=m=None

def load_hardware(replay=False):
    global owner,safe,OUT,probe,m
    if sys.platform!='win32':
        raise RuntimeError('Windows hardware backend is not available on this platform; use tools/run_offline_checks.py')
    if owner is None:
        from bridge_windows import load_owner
        owner=load_owner();safe=owner.safe;OUT=owner.OUT
    if replay and probe is None:
        probe=module('probe','test-pico-bridge-v040.py');m=probe.m

def child(bp,rp):
    load_hardware(replay=True)
    report={'status':'INCOMPLETE','frames':0,'nonneutral_frames':0,'maximum_offset':0,'events':0,'wire_trace':[]}
    b=json.loads(bp.read_text(encoding='utf-8'));r=None;client=None;dirty=False
    stop=threading.Event();thread=None;inbox=queue.Queue(maxsize=512);timer=False
    try:
        probe.open_candidate();ep=probe.endpoint()
        client=Client(ep['ip'],int(ep['session'],16));renderer=Renderer()
        def collect():
            try:
                while not stop.is_set():
                    frame=client.poll()
                    if frame:inbox.put_nowait(frame)
                    time.sleep(.004)
            except BaseException as e:
                try:inbox.put_nowait(e)
                except queue.Full:stop.set()
        thread=threading.Thread(target=collect);thread.start()
        m.send(0x80,b'\4');m.sub(3,b'\x30');m.sub(0x40,b'\2');m.sub(0x48,b'\1')
        deadline=time.perf_counter()+2
        while not renderer.upstream_seen:
            frame=inbox.get(timeout=max(.001,deadline-time.perf_counter()))
            if isinstance(frame,BaseException):raise frame
            renderer.feed(frame)
        # Capture integrity and complete prefix are mandatory, not a synthetic tone.
        capture=json.loads((OUT/'pico-continuous-capture-20261022-140937.json').read_text(encoding='utf-8'))['newest']
        if not capture['complete'] or capture['dropped_events']:raise ValueError('Incomplete source')
        events=[e for e in capture['events'] if e['motors_hex'] is not None and e['at_us']<=4200000]
        if not events:raise ValueError('No capture prefix')
        r=safe.open_reader({});owner.identity(r,b)
        before={};owner.verify(r,b,before)
        if not before['configuration_unchanged']:raise ValueError('Configuration changed before output')
        r.allowed_modes=owner.MODES;timer=TimerResolution();timer.start()
        dirty=True;r.mode(b'\x01\x12\x02\x40\x00')
        start=time.perf_counter();origin=events[0]['at_us'];index=0;block=0
        duration=(events[-1]['at_us']-origin)/1e6+.25
        if not .1<duration<5:raise ValueError('Replay duration bounds')
        while time.perf_counter()-start<duration:
            target=start+block*.008;now=time.perf_counter()
            if now>target+.016:raise BridgeFault('host scheduler late; no burst catch-up')
            if now<target:time.sleep(target-now)
            now=time.perf_counter()
            while index<len(events) and (events[index]['at_us']-origin)/1e6<=now-start:
                m.send(0x10,bytes([index%16])+bytes.fromhex(events[index]['motors_hex']));index+=1
            while not inbox.empty():
                frame=inbox.get_nowait()
                if isinstance(frame,BaseException):raise frame
                report['events']+=len(frame['events'])
                for ev in frame['events']:
                    report['wire_trace'].append(dict(at_us=ev['at_us'],sequence=ev['sequence'],motors=ev['motors'].hex(),received=frame['received_at']-start,rtt_ms=frame['rtt_ms']))
                renderer.feed(frame)
            if stop.is_set():raise BridgeFault('collector stopped')
            left,right=renderer.block(target);offset=max(abs(v-128) for v in left+right)
            report['maximum_offset']=max(report['maximum_offset'],offset)
            report['nonneutral_frames']+=bool(offset)
            r.stream(safe.waveform(left,right));report['frames']+=1;block+=1
        report.update(sent_raw_events=index,active_samples=renderer.active_total)
        if index!=len(events) or not report['nonneutral_frames'] or not all(renderer.active_total):raise ValueError('Did not render both captured sides')
        report['status']='PASSED_PICO_WIFI_FLYDIGI_BENCH'
    except BaseException as e:report['error']=repr(e)
    finally:
        stop.set()
        if thread:thread.join(timeout=1)
        if client:client.close()
        if r and dirty:
            try:owner.stop(r,report)
            except BaseException as e:report['cleanup_error']=repr(e)
        if r:r.close()
        if m.handle:
            try:
                if m.verified:m.send(0x80,b'\xfeRESETLAB')
            except BaseException as e:report['pico_reset_error']=repr(e)
            m.lib.hid_close(m.handle);m.handle=None
        m.lib.hid_exit()
        if timer:timer.close()
        rp.write_text(json.dumps(report,indent=2),encoding='utf-8')
    return 0 if report['status']=='PASSED_PICO_WIFI_FLYDIGI_BENCH' else 1

def main(live=False,prompt_ms=0,prompt_offset=3,game_pilot=False):
    load_hardware()
    stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    bp=OUT/f'flydigi-live-bench-backup-{stamp}.json';cp=OUT/f'flydigi-live-bench-child-{stamp}.json'
    report=dict(status='INCOMPLETE',persistent_write_commands=0,maximum_allowed_offset=5,
        path='PC captured USB reports -> RAM Pico -> actual WiFi -> PC decode -> Flydigi',
        actual_switch_live_test=False,automatic_resume=False,parent_guardian=True)
    if live:report.update(path='Switch USB -> Pico -> actual WiFi -> PC decode -> Flydigi',actual_switch_live_test=True)
    report['prompt_ms']=prompt_ms
    if prompt_ms:report['maximum_allowed_offset']=prompt_offset
    report['prompt_offset']=prompt_offset
    report['game_pilot']=game_pilot
    r=None;b=None;proc=None;dirty=False
    try:
        r=safe.open_reader(report);b=owner.backup(r,bp);r.close();r=None
        dirty=True
        entry=HERE/'bridge-switch-live.py' if live else pathlib.Path(__file__).absolute()
        args=[sys.executable,str(entry),'--child',str(bp),str(cp)]
        if live:args+=['--prompt-ms',str(prompt_ms),'--prompt-offset',str(prompt_offset)]
        if game_pilot:args+=['--game-pilot']
        proc=subprocess.Popen(args,
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
        stdout,stderr,killed=communicate_bounded(proc,(200 if game_pilot else 155) if live else 38)
        if killed:report['guardian_killed_late_child']=True
        report['child_exit']=proc.returncode;report['child_error']=stderr[-1500:]
        if cp.exists():report['child']=json.loads(cp.read_text(encoding='utf-8'))
        r=safe.open_reader(report);owner.identity(r,b);owner.stop(r,report);dirty=False;owner.verify(r,b,report)
        if not killed and child_succeeded(report.get('child'),proc.returncode,live) and report['configuration_unchanged'] and report['runtime_disable_ack']:
            report['status']='PASSED_SWITCH_LIVE_AND_CONFIG_RECHECK' if live else 'PASSED_BOUNDED_LIVE_BENCH_AND_CONFIG_RECHECK'
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
        path=OUT/f'flydigi-live-bench-{stamp}.json';path.write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report,indent=2));print(str(path))
    return 0 if report['status'] in ('PASSED_BOUNDED_LIVE_BENCH_AND_CONFIG_RECHECK','PASSED_SWITCH_LIVE_AND_CONFIG_RECHECK') else 1
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--child',nargs=2,metavar=('BACKUP','REPORT'))
    args=parser.parse_args()
    if sys.platform!='win32':parser.error('Windows hardware backend unavailable; offline checks are supported on Mac')
    if args.child:raise SystemExit(child(pathlib.Path(args.child[0]),pathlib.Path(args.child[1])))
    raise SystemExit(main())
