"""Bounded host-only replay. Fake source/output, no sockets or device libraries."""
import argparse,ctypes,json,pathlib,queue,struct,sys,tempfile,threading,time,zlib
ROOT=pathlib.Path(__file__).absolute().parents[1];sys.path.insert(0,str(ROOT/'handoff/2026-10-22/work'))
from bridge_protocol import unpack
from sustained_game_session import SustainedGameSession
from dispatch_windows_entry import ObservedGame,AsyncPhasePath
from outer_loop_probe import GameProxy,TimeProxy,PhasePath,MarkerPath
from retained_outer_gap import RetainingProbe as OuterLoopProbe,bind_to_fault
from sustained_validation import assess_sustained
from software_replay_source import NEUTRAL,schedule as source_schedule

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=pathlib.Path,required=True);p.add_argument('--wait-mode',choices=('sleep','highres','spin'),default='sleep');p.add_argument('--pulse-ms',type=int,choices=(8,280),default=8);p.add_argument('--archived-program',type=pathlib.Path);a=p.parse_args()
    if a.output.exists():raise ValueError('Evidence exists')
    excerpt=None;source_metadata=None
    if a.archived_program:
        if a.pulse_ms!=8:raise ValueError('Archived source cannot combine with pulse profile')
        import hashlib
        from archived_software_source import prepare,START_INDEX,END_INDEX
        source_bytes=a.archived_program.read_bytes()
        excerpt=prepare(json.loads(source_bytes.decode('utf-8'))['child']['events'])
        source_metadata=dict(source_sha256=hashlib.sha256(source_bytes).hexdigest(),
            excerpt_indices=[START_INDEX,END_INDEX],end_index_exclusive=True,
            motor_bytes_and_intra_excerpt_intervals_preserved=True,
            decoder_state_matches_full_archive=True,repeat_decoder_state_verified=True,
            repetitions=6,repetitions_and_time_shifts_synthetic=True,
            packet_envelopes_sequences_and_grouping_synthetic=True,initial_neutral_field_synthetic=True)

    def audit(event,args):
        if event.startswith('socket.') or event in ('subprocess.Popen','os.system','os.startfile'):raise PermissionError(event)
        if event=='ctypes.dlopen' and str(args[0]).lower() not in (('winmm','kernel32') if a.wait_mode=='highres' else ('winmm',)):raise PermissionError('Only software timer library permitted')
    sys.addaudithook(audit);lib=ctypes.WinDLL('winmm');lib.timeBeginPeriod.argtypes=[ctypes.c_uint];lib.timeBeginPeriod.restype=ctypes.c_uint;lib.timeEndPeriod.argtypes=[ctypes.c_uint];lib.timeEndPeriod.restype=ctypes.c_uint
    report=dict(status='INCOMPLETE',hardware_actions=0,network_actions=0,physical_output=False,fake_stop_ack=True,source_fields_synthetic=True,source_timeline_synthetic=True,wait_mode=a.wait_mode,synthetic_pulse_ms=a.pulse_ms if excerpt is None else None,archived_source=source_metadata)
    begin=lib.timeBeginPeriod(1);report['timer_begin']=begin;stop=threading.Event();inbox=queue.Queue(maxsize=512);arm=[None];worker=None;game=None;phase=None;stops=[];origin=time.perf_counter();collector_errors=[];highres=None;spin=None;cpu_start=time.process_time();wall_start=time.perf_counter()
    with tempfile.TemporaryDirectory(prefix='software-loop-',dir=str(a.output.parent)) as temp:
        try:
            if begin:raise RuntimeError('Timer acquisition failed')
            base_time=time
            if a.wait_mode=='spin':
                from offline_spin_adapter import SpinTime
                spin=SpinTime(time,lambda:game);base_time=spin
            if a.wait_mode=='highres':
                from highres_wait_candidate import HighResolutionWait,blocking_request
                highres=HighResolutionWait()
                class BaseTime:
                    def __getattr__(self,name):return getattr(time,name)
                    def sleep(self,seconds):
                        if seconds!=.001:return time.sleep(seconds)
                        active=game is not None and game.output.renderer.armed and game.output.dirty and not game.output.fault
                        duration=blocking_request(time.perf_counter(),game.target if game is not None else None,active)
                        if duration:highres.sleep(duration)
                base_time=BaseTime()
            probe=OuterLoopProbe();phase=AsyncPhasePath(pathlib.Path(temp)/'phase.json');phase_proxy=PhasePath(phase,probe);cancel=MarkerPath(pathlib.Path(temp)/'arm',probe).with_suffix('.cancel');timer=TimeProxy(base_time,probe)
            inner=SustainedGameSession(lambda:None,lambda l,r:None,lambda:(stops.append(time.perf_counter()) or dict(runtime_disable_ack=True)))
            game=GameProxy(ObservedGame(inner,phase.publisher),probe)
            def collect():
                seq=0;sent_initial=False;index=0;schedule=None
                try:
                    while not stop.is_set():
                        now=time.perf_counter();stamp=round((now-origin)*1e6);events=[]
                        if not sent_initial:events.append((stamp,seq,NEUTRAL));seq+=1;sent_initial=True
                        if arm[0] is not None and schedule is None:
                            if excerpt is None:schedule=source_schedule(arm[0],origin,a.pulse_ms)
                            else:
                                from archived_software_source import schedule as archived_schedule
                                schedule=archived_schedule(excerpt,arm[0],origin)
                        while schedule and index<len(schedule) and schedule[index][0]<=stamp:
                            at,raw=schedule[index];events.append((at,seq,raw));seq+=1;index+=1
                        data=struct.pack('<4sBBHQIIIHH',b'BHR2',2,7,36+16*len(events),1,42,99,stamp,len(events),0)+b''.join(struct.pack('<II8s',*e) for e in events)
                        f=unpack(data+struct.pack('<I',zlib.crc32(data)),1,42);f['received_at']=time.perf_counter();inbox.put_nowait(f);time.sleep(.004)
                except BaseException as exc:collector_errors.append(type(exc).__name__);stop.set()
            worker=threading.Thread(target=collect,daemon=True);worker.start();started=time.perf_counter();last_ui=0.
            while time.perf_counter()-started<65:
                if cancel.exists():raise RuntimeError('Synthetic cancel')
                while not inbox.empty():game.feed(inbox.get_nowait())
                if collector_errors:raise RuntimeError('Synthetic collector failed')
                if arm[0] is None and game.source_ready():game.arm(True,time.perf_counter()-started);arm[0]=game.output.renderer.armed_at
                now=time.perf_counter()
                if now-last_ui>=.2:
                    phase_proxy.write_text(json.dumps(dict(phase='ARMED' if arm[0] is not None else 'WAITING_SOURCE',clock='monotonic',completed_events=game.output.renderer.completed_events)));last_ui=now
                game.tick()
                if game.output.fault or game.output.stopped_at is not None:break
                timer.sleep(.001)
            report.update(game=game.summary(),outer_loop=probe.summary(),stop_callbacks=len(stops),collector_errors=collector_errors)
            report['fault_gap_binding']=bind_to_fault(report['outer_loop']['last_gap'],report['game'].get('dispatch_io',{}).get('first_fault'))
            report['full_window_validation']=assess_sustained(report['game'])
            report['status']='HOST_SOFTWARE_FULL_WINDOW_PASSED' if report['full_window_validation']['passed'] else 'HOST_SOFTWARE_REPLAY_INCOMPLETE'
        except BaseException as exc:report['error']=type(exc).__name__
        finally:
            if game:
                try:game.output.stop()
                except BaseException as exc:report['stop_error']=type(exc).__name__
            stop.set()
            if worker:worker.join(1);report['worker_joined']=not worker.is_alive()
            if phase:
                try:phase.publisher.close();report['publisher_closed']=True
                except BaseException as exc:report['publisher_error']=type(exc).__name__
            if highres:
                try:highres.close();report['highres_handle_closed']=highres.handle is None
                except BaseException as exc:report['highres_close_error']=type(exc).__name__
            if spin:report['spin_wait']=spin.summary()
            report['cpu_seconds']=time.process_time()-cpu_start;report['wall_seconds']=time.perf_counter()-wall_start
            report['timer_end']=lib.timeEndPeriod(1) if begin==0 else None
    if report.get('worker_joined') is not True or report.get('publisher_closed') is not True or report.get('timer_end')!=0 or report.get('highres_close_error'):report['status']='HOST_SOFTWARE_REPLAY_INCOMPLETE'
    report['limitations']=['Synthetic event timing/repetition and empty XInput source; no actual input/HID/network load','Fake output consumes no device write time','Host-only result cannot be substituted for Switch acceptance']
    with a.output.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
    g=report.get('game',{});print(json.dumps(dict(status=report['status'],frames=g.get('output_frames'),events=g.get('completed_events'),fault=g.get('output_fault'),lateness_seconds=(g.get('dispatch_io',{}).get('first_fault') or {}).get('lateness_seconds'),timer_end=report.get('timer_end'),worker_joined=report.get('worker_joined')),indent=2))
if __name__=='__main__':main()
