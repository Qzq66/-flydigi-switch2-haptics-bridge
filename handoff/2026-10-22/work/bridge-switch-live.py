"""Bounded actual Switch receiver, guarded by the existing Flydigi owner parent."""
import socket,struct,time,json,pathlib,threading,queue,sys,argparse
from bridge_runtime import Client,Renderer,BridgeFault,unpack,collect_frames
from importlib.util import spec_from_file_location,module_from_spec
from bridge_windows import TimerResolution
from bridge_network import DEFAULT_NETWORK
from bridge_render import GameOutputLatch,phase_frame
from bridge_session_policy import session_limits
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

def child(bp,rp,prompt_ms=0,prompt_offset=3,game_pilot=False,session_file=None,input_check_only=False,arm_file=None,phase_status_file=None,live_seconds=60,input_timing_file=None):
    limits=session_limits(live_seconds)
    load_hardware()
    report=dict(status='INCOMPLETE',events=[],frames=0,nonneutral_frames=0,maximum_offset=0)
    report.update(prompt_ms=prompt_ms,rendering_mode='calibrated notification mapping' if prompt_ms else 'original experimental parameter groups')
    report['prompt_offset']=prompt_offset
    report['game_pilot']=game_pilot;input_source=None
    report['session_limits']=limits
    staged=arm_file is not None;armed=not staged
    report.update(motor_output_enabled=not input_check_only and armed,output_frames=0,staged_game=staged)
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
        session_data=json.loads((session_file or HERE/'private/bridge-session.json').read_text(encoding='utf-8-sig'))
        session=int(session_data['session'],16)
        ip=discover(session,limits['discovery_seconds']);report['pico_ip']=ip;client=Client(ip,session,input_source=input_source);renderer=Renderer(prompt_ms=prompt_ms,prompt_offset=prompt_offset,game_pilot=game_pilot)
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
            frame['processed_at']=time.perf_counter();renderer.feed(phase_frame(frame,armed))
            for e in frame['events']:report['events'].append(dict(at_us=e['at_us'],sequence=e['sequence'],motors=e['motors'].hex(),flags=frame['flags']))
            required_flags=2 if input_check_only or staged else 6
            if frame['flags']&required_flags==required_flags:break
        if list(r.state())!=b['state_before']:raise ValueError('Controller state changed while waiting')
        r.maximum_offset=prompt_offset if prompt_ms else 5
        timer=TimerResolution();timer.start()
        if not input_check_only and armed:
            dirty=True;r.mode(b'\x01\x12\x02\x40\x00')
        def mute_output():
            nonlocal dirty
            owner.stop(r,report);dirty=False
            report['muted_at_pc_clock']=time.perf_counter()
            report['input_reads_at_mute']=input_source.nonneutral_reads if input_source else 0
            report['output_frames_at_mute']=report['output_frames']
        playback=GameOutputLatch(renderer,mute_output) if game_pilot and not input_check_only else renderer
        start=time.perf_counter();clock_start=start;block=0
        report['live_started_at_pc_clock']=start
        if input_timing_file:
            input_timing_file.write_text(json.dumps(dict(phase='INPUT_READY',clock='monotonic',started_at_monotonic=time.monotonic())),encoding='utf-8')
            report['input_timing_enabled']=True
            report['input_timing_clock']='monotonic'
        phase_deadline_monotonic=time.monotonic()+limits['ui_deadline_seconds']
        if phase_status_file:phase_status_file.write_text(json.dumps(dict(phase='INPUT_READY',clock='monotonic',deadline_monotonic=phase_deadline_monotonic)),encoding='utf-8')
        draining=False;stream_complete=False
        limit=limits['host_live_seconds'] if game_pilot else 22
        report['live_limit_seconds']=limit
        while time.perf_counter()-start<limit:
            target=clock_start+block*.008;now=time.perf_counter()
            if staged and not armed and arm_file.exists():
                from bridge_input import NEUTRAL
                if input_source()!=NEUTRAL:raise BridgeFault('Release controls before arming game output')
                if now-start>limits['arm_latest_seconds']:raise BridgeFault('Game arming window expired')
                if renderer.prompt_counts!=[0,0] or report['output_frames']!=0:raise BridgeFault('Pre-arm output was not silent')
                dirty=True;r.mode(b'\x01\x12\x02\x40\x00');armed=True
                report.update(motor_output_enabled=True,armed_at_pc_clock=time.perf_counter(),pre_arm_output_frames=report['output_frames'],pre_arm_prompt_counts=list(renderer.prompt_counts))
                if phase_status_file:phase_status_file.write_text(json.dumps(dict(phase='ARMED',clock='monotonic',deadline_monotonic=phase_deadline_monotonic)),encoding='utf-8')
                renderer.rendered_until=None;clock_start=time.perf_counter();block=0
                continue
            muted=isinstance(playback,GameOutputLatch) and playback.reason is not None
            if not draining and not muted:
                if now>target+.016:raise BridgeFault('host scheduler late; no catch-up')
                if now<target:time.sleep(target-now)
            else:time.sleep(.004)
            while not inbox.empty():
                frame=inbox.get_nowait()
                if isinstance(frame,BaseException):raise frame
                for e in frame['events']:report['events'].append(dict(at_us=e['at_us'],sequence=e['sequence'],motors=e['motors'].hex(),flags=frame['flags']))
                if frame['flags']&8:
                    if not draining:
                        if dirty:owner.stop(r,report);dirty=False
                        draining=True
                    if frame['flags']&16:stream_complete=True;break
                    continue
                if draining:raise BridgeFault('stream resumed after terminal marker')
                frame['processed_at']=time.perf_counter();playback.feed(phase_frame(frame,armed))
            if stream_complete:
                report['ended_reason']='terminal stream complete';break
            if draining:
                if time.perf_counter()-renderer.last_received>1.5:raise BridgeFault('stream drain timeout')
                block+=1;continue
            if stop.is_set():raise BridgeFault('collector stopped')
            # The stop/disable acknowledgement can block beyond one PCM slot.
            # After latching mute no waveform is sent, so use current time for
            # heartbeat checks and never try to catch up the old sample clock.
            samples=playback.block(time.perf_counter() if muted else target)
            if samples is None:
                report['muted_frames']=report.get('muted_frames',0)+1
                report['frames']+=1;block+=1;continue
            left,right=samples;offset=max(abs(v-128) for v in left+right)
            if not input_check_only and armed:
                report['maximum_offset']=max(report['maximum_offset'],offset);report['nonneutral_frames']+=bool(offset)
                r.stream(safe.waveform(left,right,maximum_offset=r.maximum_offset));report['output_frames']+=1
            report['frames']+=1;block+=1
        if not stream_complete:report['ended_reason']='bounded live deadline'
    except BaseException as e:report['ended_reason']=repr(e)
    finally:
        if 'start' in locals():report['live_elapsed_seconds']=time.perf_counter()-start
        if input_timing_file:
            try:input_timing_file.write_text(json.dumps(dict(phase='ENDED')),encoding='utf-8')
            except OSError:pass
        if phase_status_file:
            try:phase_status_file.write_text(json.dumps(dict(phase='ENDED')),encoding='utf-8')
            except OSError:pass
        stop.set()
        if thread:thread.join(timeout=1)
        report['collector_ended']=not thread or not thread.is_alive()
        if client:client.close()
        if client:report.update(terminal_received=client.terminal_received,terminal_ack_replied=client.terminal_ack_replied)
        if input_source:report['input_relay']=dict(slot=input_source.slot,nonneutral_reads=input_source.nonneutral_reads,changes=input_source.changes,
            last_pro_input=input_source.previous.hex() if input_source.previous is not None else None,last_read_at_pc_clock=getattr(input_source,'last_read_at',None),
            last_nonneutral_at_pc_clock=getattr(input_source,'last_nonneutral_at',None))
        if 'renderer' in locals():
            report['active_samples']=renderer.active_total;report['source_active_samples']=renderer.source_active_total;report['prompt_counts']=renderer.prompt_counts
            if renderer.anchor:report['source_clock_anchor']=dict(source_us=renderer.anchor[0],pc_clock=renderer.anchor[1])
        if 'playback' in locals() and isinstance(playback,GameOutputLatch):report['output_fault']=playback.reason
        if r and dirty:
            try:owner.stop(r,report)
            except BaseException as e:report['cleanup_error']=repr(e)
        if r:r.close()
        safe.ro.lib.hid_exit()
        if timer:timer.close()
        report['timer_released']=not timer or not timer.active
        # A deliberate USB end/heartbeat loss is expected at the firmware's 20s cap.
        reason=report.get('ended_reason','')
        counts=report.get('prompt_counts',[0,0])
        expected_activity=any(counts) if game_pilot else all(counts)
        complete_prompt=(not prompt_ms or (expected_activity and report.get('active_samples')==[120*n for n in counts]))
        if input_check_only:
            if reason=='terminal stream complete' and report.get('terminal_received') and report.get('terminal_ack_replied') and report['collector_ended'] and report['timer_released'] and report.get('input_relay',{}).get('nonneutral_reads',0)>0 and not report.get('cleanup_error'):
                report['status']='PASSED_SWITCH_WIFI_INPUT_END_CHECK'
        elif game_pilot:
            if reason=='terminal stream complete' and report.get('terminal_received') and report.get('terminal_ack_replied') and report['collector_ended'] and report['timer_released'] and report.get('runtime_disable_ack') and complete_prompt and any(report.get('prompt_counts',[])) and not report.get('cleanup_error') and not report.get('output_fault'):
                report['status']='PASSED_SWITCH_WIFI_GAME_PILOT_PROGRAM_CHECKS'
        elif complete_prompt and report.get('active_samples') and all(report['active_samples']) and report.get('runtime_disable_ack') and not report.get('cleanup_error') and any(s in reason for s in ('terminal stream complete','USB upstream stopped','wire heartbeat timeout','bounded live deadline')):
            report['status']='PASSED_SWITCH_WIFI_FLYDIGI_LIMITED_LIVE'
        rp.write_text(json.dumps(report,indent=2),encoding='utf-8')
    return 0 if report['status'] in ('PASSED_SWITCH_WIFI_FLYDIGI_LIMITED_LIVE','PASSED_SWITCH_WIFI_INPUT_END_CHECK','PASSED_SWITCH_WIFI_GAME_PILOT_PROGRAM_CHECKS') else 1

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--child',nargs=2,metavar=('BACKUP','REPORT'))
    p.add_argument('--prompt-ms',type=int,choices=(0,120),default=0);p.add_argument('--prompt-offset',type=int,choices=(3,5,8,12),default=3);p.add_argument('--game-pilot',action='store_true')
    p.add_argument('--session-file',type=pathlib.Path);p.add_argument('--input-check-only',action='store_true');p.add_argument('--arm-file',type=pathlib.Path);p.add_argument('--phase-status-file',type=pathlib.Path)
    p.add_argument('--input-timing-file',type=pathlib.Path)
    p.add_argument('--live-seconds',type=int,choices=(60,120),default=60);a=p.parse_args()
    if a.input_timing_file and (not a.child or not a.input_check_only or a.live_seconds!=120):p.error('Timing display requires the 120s input-only child')
    if a.live_seconds!=60 and (not a.child or not a.game_pilot):p.error('Extended duration requires a guarded game-pilot child')
    if bool(a.arm_file)!=bool(a.phase_status_file):p.error('Both staged-game paths are required')
    if a.arm_file and (not a.child or not a.game_pilot or a.input_check_only):p.error('Staged output requires a guarded game child')
    if a.input_check_only and not a.game_pilot:p.error('--input-check-only requires --game-pilot')
    if (a.session_file or a.input_check_only) and not a.child:p.error('Explicit session/input-check options require the strict child launcher')
    if a.game_pilot and a.prompt_ms!=120:p.error('--game-pilot requires --prompt-ms 120')
    if not a.prompt_ms and a.prompt_offset!=3:p.error('--prompt-offset requires --prompt-ms 120')
    if sys.platform!='win32':p.error('Windows hardware backend unavailable; offline checks are supported on Mac')
    load_hardware()
    if a.child:raise SystemExit(child(pathlib.Path(a.child[0]),pathlib.Path(a.child[1]),a.prompt_ms,a.prompt_offset,a.game_pilot,a.session_file,a.input_check_only,a.arm_file,a.phase_status_file,a.live_seconds,a.input_timing_file))
    raise SystemExit(bench.main(live=True,prompt_ms=a.prompt_ms,prompt_offset=a.prompt_offset,game_pilot=a.game_pilot))
