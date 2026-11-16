"""Offline real motor-field workload; UDP headers/batching are synthetic."""
import argparse,json,pathlib,struct,zlib,time,statistics,sys,ctypes,threading
ROOT=pathlib.Path(__file__).absolute().parents[1];sys.path.insert(0,str(ROOT/'handoff/2026-10-22/work'))
from bridge_protocol import unpack
from switch_hd_decode import Decoder
from sustained_game_session import SustainedGameSession

def packets(events):
    result=[];index=0
    while index<len(events):
        flags=events[index]['flags'];group=[]
        while index<len(events) and len(group)<8 and events[index]['flags']==flags:group.append(events[index]);index+=1
        stamp=group[-1]['at_us'];header=struct.pack('<4sBBHQIIIHH',b'BHR2',2,flags,36+16*len(group),1,42,99,stamp,len(group),0)
        body=header+b''.join(struct.pack('<II8s',e['at_us'],e['sequence'],bytes.fromhex(e['motors'])) for e in group)
        result.append(body+struct.pack('<I',zlib.crc32(body)))
    return result

def stats(values):
    if not values:return dict(samples=0,p50_us=None,p99_us=None,max_us=None,over4ms=0)
    v=sorted(values)
    return dict(samples=len(v),p50_us=statistics.median(v)*1e6,p99_us=v[int((len(v)-1)*.99)]*1e6,max_us=max(v)*1e6,over4ms=sum(x>.004 for x in v))

def profile(events,rounds=20):
    raw=packets(events);parsed=[unpack(p,1,42) for p in raw]
    assert [e['motors'].hex() for f in parsed for e in f['events']]==[e['motors'] for e in events]
    parse=[];decode=[];feed=[];bursts=[]
    for _ in range(rounds):
        dec=[Decoder(),Decoder()];now=[0.]
        def forbidden(*a):raise AssertionError('No output is allowed in workload profile')
        game=SustainedGameSession(forbidden,forbidden,forbidden,clock=lambda:now[0]);origin=parsed[0]['source_us']
        batch=[]
        for data,frame in zip(raw,parsed):
            start=time.perf_counter();unpack(data,1,42);parse.append(time.perf_counter()-start)
            for e in frame['events']:
                start=time.perf_counter();dec[0].decode(e['motors'][:4]);dec[1].decode(e['motors'][4:]);decode.append(time.perf_counter()-start)
            now[0]=1.+(frame['source_us']-origin)/1e6;packet=dict(frame,received_at=now[0],processed_at=now[0]);start=time.perf_counter();game.feed(packet);duration=time.perf_counter()-start;feed.append(duration);batch.append(duration)
            if len(batch)==8:bursts.append(sum(batch));batch=[]
        assert game.output.fault is None and game.output.frames==0 and not game.output.dirty
    return dict(source_events=len(events),synthetic_packets=len(raw),rounds=rounds,parse=stats(parse),two_side_decode=stats(decode),unarmed_game_feed=stats(feed),sum_of_eight_feed_calls=stats(bursts),scope='Real archived motor fields; headers and packet grouping synthetic. Unarmed feed includes quiet qualification, excludes active heap scheduling/HID and XInput.')

def host_timing(raw):
    import ctypes,threading
    lib=ctypes.WinDLL('winmm');lib.timeBeginPeriod.argtypes=[ctypes.c_uint];lib.timeBeginPeriod.restype=ctypes.c_uint;lib.timeEndPeriod.argtypes=[ctypes.c_uint];lib.timeEndPeriod.restype=ctypes.c_uint
    result=dict(begin=lib.timeBeginPeriod(1))
    try:
        if result['begin']:raise RuntimeError('Timer acquisition failed')
        def run(mode):
            stop=threading.Event();worker=None
            def work():
                i=0;end=time.perf_counter()+2
                while not stop.is_set() and time.perf_counter()<end:
                    unpack(raw[i%len(raw)],1,42);i+=1
                    if mode=='paced':time.sleep(.004)
            if mode!='baseline':worker=threading.Thread(target=work,daemon=True);worker.start()
            start=time.perf_counter();target=start+.008;late=[];fault=None
            try:
                while len(late)<100:
                    now=time.perf_counter()
                    if now>=target:
                        if now-target>.004:fault=(now-target)*1000;break
                        late.append((now-target)*1000);target+=.008
                    else:time.sleep(.001)
            finally:
                stop.set()
                if worker:worker.join(1)
            return dict(deadlines=len(late),first_late_fault_ms=fault,max_successful_lateness_ms=max(late) if late else None,worker_joined=worker is None or not worker.is_alive())
        result.update(baseline=run('baseline'),paced_4ms_parser=run('paced'),saturated_parser=run('saturated'))
    finally:result['end']=lib.timeEndPeriod(1) if result['begin']==0 else None
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--program',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,required=True);p.add_argument('--host-timing',action='store_true');a=p.parse_args()
    if a.output.exists():raise ValueError('Refusing evidence overwrite')
    def audit(event,args):
        if event.startswith('socket.') or event in ('subprocess.Popen','os.system','os.startfile'):raise PermissionError(event)
        if event=='ctypes.dlopen' and (not a.host_timing or str(args[0]).lower()!='winmm'):raise PermissionError('Native backend denied')
    sys.addaudithook(audit);events=json.loads(a.program.read_text(encoding='utf-8'))['child']['events'];r=profile(events)
    r.update(status='ARCHIVED_PAYLOAD_PROFILE_ONLY',hardware_actions=0,network_actions=0,original_packet_headers_available=False,product_code_changed=False)
    if a.host_timing:r['host_timing']=host_timing(packets(events))
    with a.output.open('x',encoding='utf-8') as f:json.dump(r,f,indent=2)
    print(json.dumps(r,indent=2))
if __name__=='__main__':main()
