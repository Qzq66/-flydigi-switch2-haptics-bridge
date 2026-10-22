"""Bounded actual Switch receiver, guarded by the existing Flydigi owner parent."""
import socket,struct,time,json,pathlib,threading,queue,sys,argparse
from bridge_runtime import Client,Renderer,BridgeFault,unpack,collect_frames
from importlib.util import spec_from_file_location,module_from_spec
from bridge_windows import TimerResolution
from bridge_network import DEFAULT_NETWORK
HERE=pathlib.Path(__file__).absolute().parent
bench=owner=safe=OUT=None

def load_hardware():
    global bench,owner,safe,OUT
    if sys.platform!='win32':
        raise RuntimeError('Windows hardware backend is not available on this platform; use tools/run_offline_checks.py')
    if bench is None:
        spec=spec_from_file_location('bench',HERE/'flydigi-live-bridge-bench.py')
        bench=module_from_spec(spec);spec.loader.exec_module(bench)
        bench.load_hardware();owner=bench.owner;safe=bench.safe;OUT=bench.OUT

def discover(session,timeout=60,network=DEFAULT_NETWORK):
    sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET,socket.SO_BROADCAST,1);sock.bind((network.bind_host,0));sock.settimeout(.3)
        end=time.perf_counter()+timeout;request=0
        while time.perf_counter()<end:
            request+=1;sock.sendto(struct.pack('<4sIQI',b'BHP2',request,session,0xffffffff),(network.broadcast,network.port))
            try:data,peer=sock.recvfrom(512)
            except socket.timeout:continue
            if not network.accepts(peer):continue
            try:unpack(data,session,request)
            except BridgeFault:continue
            return peer[0]
        raise TimeoutError('No matching Pico within connection window')
    finally:sock.close()

def child(bp,rp,prompt_ms=0,prompt_offset=3,game_pilot=False):
    load_hardware()
    report=dict(status='INCOMPLETE',events=[],frames=0,nonneutral_frames=0,maximum_offset=0)
    report.update(prompt_ms=prompt_ms,rendering_mode='calibrated notification mapping' if prompt_ms else 'original experimental parameter groups')
    report['prompt_offset']=prompt_offset
    report['game_pilot']=game_pilot;input_source=None
    b=json.loads(bp.read_text(encoding='utf-8'));r=None;client=None;dirty=False;timer=False;thread=None
    stop=threading.Event();inbox=queue.Queue(maxsize=512)
    try:
        # Complete slow configuration reads before the first network poll can
        # arm the Pico's one-shot registration and prompt haptics.
        r=safe.open_reader({});owner.identity(r,b);before={};owner.verify(r,b,before)
        if not before['configuration_unchanged']:raise ValueError('Configuration changed before waiting')
        r.allowed_modes=owner.MODES
        if game_pilot:
            from bridge_input import XInputSource,NEUTRAL
            input_source=XInputSource();neutral_since=None;until=time.perf_counter()+5
            while time.perf_counter()<until:
                now=time.perf_counter()
                if input_source()==NEUTRAL:
                    if neutral_since is None:neutral_since=now
                    if now-neutral_since>=.5:break
                else:neutral_since=None
                time.sleep(.01)
            else:raise BridgeFault('Release all buttons and center sticks before game pilot')
        session_data=json.loads((HERE/'private/bridge-session.json').read_text(encoding='utf-8-sig'))
        session=int(session_data['session'],16)
        ip=discover(session,120);report['pico_ip']=ip;client=Client(ip,session,input_source=input_source);renderer=Renderer(prompt_ms=prompt_ms,prompt_offset=prompt_offset,game_pilot=game_pilot)
        def collect():
            try:
                collect_frames(client,inbox.put_nowait,stop.is_set)
            except BaseException as e:
                try:inbox.put_nowait(e)
                except queue.Full:stop.set()
        thread=threading.Thread(target=collect);thread.start()
        until=time.perf_counter()+5
        while True:
            frame=inbox.get(timeout=max(.001,until-time.perf_counter()))
            if isinstance(frame,BaseException):raise frame
            frame['processed_at']=time.perf_counter();renderer.feed(frame)
            for e in frame['events']:report['events'].append(dict(at_us=e['at_us'],sequence=e['sequence'],motors=e['motors'].hex(),flags=frame['flags']))
            if frame['flags']&6==6:break
        if list(r.state())!=b['state_before']:raise ValueError('Controller state changed while waiting')
        r.maximum_offset=prompt_offset if prompt_ms else 5
        timer=TimerResolution();timer.start()
        dirty=True;r.mode(b'\x01\x12\x02\x40\x00');start=time.perf_counter();block=0
        draining=False;stream_complete=False
        limit=62 if game_pilot else 22
        report['live_limit_seconds']=limit
        while time.perf_counter()-start<limit:
            target=start+block*.008;now=time.perf_counter()
            if not draining:
                if now>target+.016:raise BridgeFault('host scheduler late; no catch-up')
                if now<target:time.sleep(target-now)
            else:time.sleep(.004)
            while not inbox.empty():
                frame=inbox.get_nowait()
                if isinstance(frame,BaseException):raise frame
                for e in frame['events']:report['events'].append(dict(at_us=e['at_us'],sequence=e['sequence'],motors=e['motors'].hex(),flags=frame['flags']))
                if frame['flags']&8:
                    if not draining:
                        owner.stop(r,report);dirty=False;draining=True
                    if frame['flags']&16:stream_complete=True;break
                    continue
                if draining:raise BridgeFault('stream resumed after terminal marker')
                frame['processed_at']=time.perf_counter();renderer.feed(frame)
            if stream_complete:
                report['ended_reason']='terminal stream complete';break
            if draining:
                if time.perf_counter()-renderer.last_received>1.5:raise BridgeFault('stream drain timeout')
                block+=1;continue
            if stop.is_set():raise BridgeFault('collector stopped')
            left,right=renderer.block(target);offset=max(abs(v-128) for v in left+right)
            report['maximum_offset']=max(report['maximum_offset'],offset);report['nonneutral_frames']+=bool(offset)
            r.stream(safe.waveform(left,right,maximum_offset=r.maximum_offset));report['frames']+=1;block+=1
        if not stream_complete:report['ended_reason']='bounded live deadline'
    except BaseException as e:report['ended_reason']=repr(e)
    finally:
        stop.set()
        if thread:thread.join(timeout=1)
        if client:client.close()
        if client:report.update(terminal_received=client.terminal_received,terminal_ack_replied=client.terminal_ack_replied)
        if input_source:report['input_relay']=dict(slot=input_source.slot,nonneutral_reads=input_source.nonneutral_reads,changes=input_source.changes)
        if 'renderer' in locals():
            report['active_samples']=renderer.active_total;report['source_active_samples']=renderer.source_active_total;report['prompt_counts']=renderer.prompt_counts
        if r and dirty:
            try:owner.stop(r,report)
            except BaseException as e:report['cleanup_error']=repr(e)
        if r:r.close()
        safe.ro.lib.hid_exit()
        if timer:timer.close()
        # A deliberate USB end/heartbeat loss is expected at the firmware's 20s cap.
        reason=report.get('ended_reason','')
        complete_prompt=(not prompt_ms or (all(report.get('prompt_counts',[0,0])) and report.get('active_samples')==[120*n for n in report['prompt_counts']]))
        if complete_prompt and report.get('active_samples') and all(report['active_samples']) and report.get('runtime_disable_ack') and not report.get('cleanup_error') and any(s in reason for s in ('terminal stream complete','USB upstream stopped','wire heartbeat timeout','bounded live deadline')):
            report['status']='PASSED_SWITCH_WIFI_FLYDIGI_LIMITED_LIVE'
        rp.write_text(json.dumps(report,indent=2),encoding='utf-8')
    return 0 if report['status']=='PASSED_SWITCH_WIFI_FLYDIGI_LIMITED_LIVE' else 1

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--child',nargs=2,metavar=('BACKUP','REPORT'))
    p.add_argument('--prompt-ms',type=int,choices=(0,120),default=0);p.add_argument('--prompt-offset',type=int,choices=(3,5,8,12),default=3);p.add_argument('--game-pilot',action='store_true');a=p.parse_args()
    if a.game_pilot and a.prompt_ms!=120:p.error('--game-pilot requires --prompt-ms 120')
    if not a.prompt_ms and a.prompt_offset!=3:p.error('--prompt-offset requires --prompt-ms 120')
    if sys.platform!='win32':p.error('Windows hardware backend unavailable; offline checks are supported on Mac')
    load_hardware()
    if a.child:raise SystemExit(child(pathlib.Path(a.child[0]),pathlib.Path(a.child[1]),a.prompt_ms,a.prompt_offset,a.game_pilot))
    raise SystemExit(bench.main(live=True,prompt_ms=a.prompt_ms,prompt_offset=a.prompt_offset,game_pilot=a.game_pilot))
