"""No Flydigi access: measure real current-client timing, preserving nonce privately."""
import argparse,datetime,hashlib,importlib.util,json,pathlib,statistics,struct,sys,time
ROOT=pathlib.Path(__file__).absolute().parents[1];WORK=ROOT/'handoff/2026-10-22/work';sys.path.insert(0,str(WORK))
from bridge_transport import Client
from bridge_input import NEUTRAL
from bridge_render import collect_frames
from bridge_windows import TimerResolution
from bridge_network import NetworkConfig,DEFAULT_NETWORK
from bridge_retry_socket import RetrySocket
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--network-config',type=pathlib.Path);parser.add_argument('--compare-retries',action='store_true');args=parser.parse_args()
network=NetworkConfig(**json.loads(args.network_config.read_text(encoding='utf-8-sig'))) if args.network_config else DEFAULT_NETWORK
spec=importlib.util.spec_from_file_location('probe042',WORK/'test-pico-bridge-v042.py');probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe);m=probe.m
stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S');trace=[];phases=[];client=None;timer=TimerResolution()
report=dict(status='INCOMPLETE',flydigi_access=False,motor_output=False,persistent_writes=0,phases=phases)
class TraceSocket:
    def __init__(self,inner):self.inner=inner
    def __getattr__(self,name):return getattr(self.inner,name)
    def sendto(self,data,peer):
        result=self.inner.sendto(data,peer);trace.append(dict(direction='tx',at=time.perf_counter(),hex=data.hex()));return result
    def recvfrom(self,*args):
        data,peer=self.inner.recvfrom(*args);trace.append(dict(direction='rx',at=time.perf_counter(),hex=data.hex()));return data,peer
def percentile(values,p):return sorted(values)[min(len(values)-1,int((len(values)-1)*p))] if values else None
try:
    probe.open_candidate();ep=probe.endpoint(network,timeout=60);m.send(0x80,b'\4');m.sub(3,b'\x30');m.sub(0x40,b'\2');m.sub(0x48,b'\1')
    if not timer.start():raise RuntimeError('Timer acquisition failed')
    client=Client(ep['ip'],int(ep['session'],16),network=network);client.sock=TraceSocket(client.sock)
    phases_to_run=[('BHP2',None,False),('BHI2_neutral',lambda:NEUTRAL,False)]
    if args.compare_retries:phases_to_run += [('BHP2_same_request_retries',None,True),('BHI2_same_request_retries',lambda:NEUTRAL,True)]
    traced=client.sock;retrying=RetrySocket(traced)
    for name,source,retry in phases_to_run:
        client.sock=retrying if retry else traced
        client.input_source=source;start=time.perf_counter();received=[];rtts=[];timeouts=0;calls=0
        while time.perf_counter()-start<(12 if args.compare_retries else 15):
            frame=client.poll();calls+=1
            if frame:received.append(frame['received_at']);rtts.append(frame['rtt_ms'])
            else:timeouts+=1
            time.sleep(.004)
        gaps=[(b-a)*1000 for a,b in zip(received,received[1:])]
        phase=dict(name=name,seconds=time.perf_counter()-start,polls=calls,valid_replies=len(received),poll_timeouts=timeouts,gap_ms_median=statistics.median(gaps) if gaps else None,gap_ms_p95=percentile(gaps,.95),gap_ms_max=max(gaps) if gaps else None,gaps_over_80ms=sum(g>80 for g in gaps),rtt_ms_p95=percentile(rtts,.95),rtt_ms_max=max(rtts) if rtts else None)
        phase['same_request_retries']=retry;phase['retry_count_cumulative']=retrying.retries
        phases.append(phase);print(json.dumps(phase),flush=True)
    metrics=m.read_range(0x9240,40)
    if metrics[:4]==b'TMD1':
        values=struct.unpack_from('<ii7I',metrics,4)
        report['pico_metrics']=dict(zip(('pm_set_result','pm_get_result','pm_value','max_poll_gap_us','poll_gaps_over_2ms','max_request_gap_us','callback_count','last_send_result','max_poll_work_us'),values))
        report['pico_metrics']['observed_power_save_mode']=values[2]&15
    m.send(0x80,b'\xfcENDLAB42');terminal=[];end_deadline=time.perf_counter()+3
    collect_frames(client,lambda f:terminal.append(f['flags']),lambda:time.perf_counter()>end_deadline)
    report.update(status='TIMING_MEASURED',terminal_flags=terminal,terminal_ack_replied=client.terminal_ack_replied)
except BaseException as exc:report['error']=repr(exc)
finally:
    if client:client.close()
    if m.handle:
        try:
            if m.verified and not (client and client.terminal_received):m.send(0x80,b'\xfeRESETLAB')
        except BaseException as exc:report['reset_error']=repr(exc)
        m.lib.hid_close(m.handle)
    m.lib.hid_exit();timer.close()
    private=WORK/'private';raw=private/('network-timing-'+stamp+'.json');raw.write_text(json.dumps(trace),encoding='utf-8')
    pending={};late=0;matched=0;unknown=0
    for packet in trace:
        data=bytes.fromhex(packet['hex'])
        if packet['direction']=='tx':pending[struct.unpack_from('<I',data,4)[0]]=packet['at'];last=struct.unpack_from('<I',data,4)[0]
        elif len(data)>=20:
            request=struct.unpack_from('<I',data,16)[0]
            if request in pending:
                matched+=1;late+=request!=last
            else:unknown+=1
    report.update(original_trace_sha256=hashlib.sha256(raw.read_bytes()).hexdigest(),received_datagrams=matched+unknown,datagrams_for_superseded_requests=late,unknown_request_datagrams=unknown,raw_trace='ignored work/private; contains session token',timer_released=not timer.active,protection_threshold_changed=False)
    output=ROOT/'docs'/('WINDOWS_NETWORK_TIMING_RECHECK_'+stamp+'.json');output.write_text(json.dumps(report,indent=2),encoding='utf-8');print(str(output))
raise SystemExit(0 if report['status']=='TIMING_MEASURED' and report.get('terminal_ack_replied') else 1)
