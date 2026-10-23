"""Captured Switch USB words through actual RAM Pico, collector, renderer and guarded output."""
import datetime,importlib.util,json,pathlib,queue,sys,threading,time
ROOT=pathlib.Path(__file__).absolute().parents[1];WORK=ROOT/'handoff/2026-10-22/work';sys.path.insert(0,str(WORK))
from bridge_runtime import Client,Renderer,BridgeFault,collect_frames
from bridge_windows import TimerResolution
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj);return obj
bench=module('bench',WORK/'flydigi-live-bridge-bench.py')

def child(bp,rp):
    bench.load_hardware();owner=bench.owner;safe=bench.safe
    probe=module('probe042',WORK/'test-pico-bridge-v042.py');m=probe.m
    b=json.loads(bp.read_text(encoding='utf-8'));report=dict(status='INCOMPLETE',events=[],frames=0,maximum_offset=0)
    r=client=thread=None;dirty=False;stop=threading.Event();inbox=queue.Queue(maxsize=512);timer=TimerResolution();seen=set()
    try:
        r=safe.open_reader({});owner.identity(r,b);owner.verify(r,b,report)
        if not report['configuration_unchanged']:raise ValueError('Configuration changed before test')
        capture=json.loads((WORK.parent/'outputs/pico-continuous-capture-20261022-140937.json').read_text(encoding='utf-8'))['newest']
        if not capture['complete'] or capture['dropped_events']:raise ValueError('Incomplete source capture')
        events=[e for e in capture['events'] if e['motors_hex'] is not None and e['at_us']<=4200000]
        duration=(events[-1]['at_us']-events[0]['at_us'])/1e6+.35
        if not .1<duration<5:raise ValueError('Replay duration out of bounds')
        probe.open_candidate();ep=probe.endpoint()
        m.send(0x80,b'\4');m.sub(3,b'\x30');m.sub(0x40,b'\2');m.sub(0x48,b'\1')
        client=Client(ep['ip'],int(ep['session'],16));renderer=Renderer(prompt_ms=120,prompt_offset=12)
        def collect():
            try:collect_frames(client,inbox.put_nowait,stop.is_set)
            except BaseException as exc:
                try:inbox.put_nowait(exc)
                except queue.Full:stop.set()
        thread=threading.Thread(target=collect);thread.start()
        def consume(frame):
            if isinstance(frame,BaseException):raise frame
            for e in frame['events']:
                if e['sequence'] not in seen:
                    seen.add(e['sequence']);report['events'].append(dict(sequence=e['sequence'],at_us=e['at_us'],motors=e['motors'].hex()))
            return frame
        first=consume(inbox.get(timeout=2));first['processed_at']=time.perf_counter();renderer.feed(first)
        r.allowed_modes=owner.MODES;r.maximum_offset=12
        if not timer.start():raise RuntimeError('Timer acquisition failed')
        dirty=True;r.mode(b'\x01\x12\x02\x40\x00');start=time.perf_counter();block=index=0
        while time.perf_counter()-start<duration:
            target=start+block*.008;now=time.perf_counter()
            if now>target+.016:raise BridgeFault('Scheduler late; no catch-up')
            if target>now:time.sleep(target-now)
            now=time.perf_counter()
            while index<len(events) and (events[index]['at_us']-events[0]['at_us'])/1e6<=now-start:
                m.send(0x10,bytes([index%16])+bytes.fromhex(events[index]['motors_hex']));index+=1
            while not inbox.empty():
                frame=consume(inbox.get_nowait());frame['processed_at']=time.perf_counter();renderer.feed(frame)
            if stop.is_set():raise BridgeFault('Collector stopped unexpectedly')
            left,right=renderer.block(target);report['maximum_offset']=max(report['maximum_offset'],max(abs(v-128) for v in left+right))
            r.stream(safe.waveform(left,right,maximum_offset=12));report['frames']+=1;block+=1
        owner.stop(r,report);dirty=False
        m.send(0x10,b'\0'+bytes.fromhex('0001404000014040'));m.send(0x80,b'\xfcENDLAB42')
        end=time.perf_counter()+3;complete=False
        while time.perf_counter()<end:
            frame=consume(inbox.get(timeout=max(.001,end-time.perf_counter())))
            if frame['flags']&16:complete=True;break
        thread.join(timeout=1)
        report.update(sent_raw_events=index,active_samples=renderer.active_total,prompt_counts=renderer.prompt_counts,terminal_received=client.terminal_received,terminal_ack_replied=client.terminal_ack_replied,collector_ended=not thread.is_alive())
        if not complete or not client.terminal_ack_replied or thread.is_alive():raise BridgeFault('Incomplete terminal handshake')
        if index!=len(events) or not all(renderer.prompt_counts) or renderer.active_total!=[120*n for n in renderer.prompt_counts]:raise BridgeFault('Incomplete two-sided captured notification')
        if [e['sequence'] for e in report['events']]!=list(range(len(report['events']))):raise BridgeFault('Sequence gap')
        owner.verify(r,b,report)
        if not report['configuration_unchanged']:raise BridgeFault('Configuration changed after output')
        report['status']='PASSED_PICO_WIFI_FLYDIGI_BENCH'
    except BaseException as exc:report['error']=repr(exc)
    finally:
        stop.set()
        if thread:thread.join(timeout=1)
        if client:client.close()
        if r and dirty:
            try:owner.stop(r,report)
            except BaseException as exc:report['cleanup_error']=repr(exc)
        if r:r.close()
        if m.handle:
            try:
                if m.verified and not (client and client.terminal_received):m.send(0x80,b'\xfeRESETLAB')
            except BaseException as exc:report['pico_reset_error']=repr(exc)
            m.lib.hid_close(m.handle)
        m.lib.hid_exit();safe.ro.lib.hid_exit();timer.close();report['timer_released']=not timer.active
        rp.write_text(json.dumps(report,indent=2),encoding='utf-8')
    return 0 if report['status']=='PASSED_PICO_WIFI_FLYDIGI_BENCH' and not report.get('cleanup_error') else 1

if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--child':raise SystemExit(child(pathlib.Path(sys.argv[2]),pathlib.Path(sys.argv[3])))
    # Reuse the actual parent guardian; keep its full RAM backup private.
    bench.load_hardware();private=WORK/'private';private.mkdir(exist_ok=True);bench.OUT=private
    bench.__file__=str(pathlib.Path(__file__).absolute());result=bench.main()
    latest=max(private.glob('flydigi-live-bench-*.json'),key=lambda p:p.stat().st_mtime)
    report=json.loads(latest.read_text(encoding='utf-8'));report.update(actual_switch_live_test=False,maximum_allowed_offset=12,prompt_ms=120,prompt_offset=12,source='verified captured Switch USB prefix injected by PC; not current game traffic',collector='current collect_frames with real sockets and end acknowledgement')
    output=ROOT/'docs'/('WINDOWS_INTEGRATED_RAM_RECHECK_'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'.json');output.write_text(json.dumps(report,indent=2),encoding='utf-8');print(str(output));raise SystemExit(result)
