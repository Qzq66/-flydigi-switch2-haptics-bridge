"""Actual v042 RAM recheck, retaining complete traffic privately and redacted events."""
import pathlib,sys,json,time,datetime,importlib.util,hashlib
ROOT=pathlib.Path(__file__).absolute().parents[1];WORK=ROOT/'handoff/2026-10-22/work';sys.path.insert(0,str(WORK))
from bridge_transport import Client
from pico_continuous_log import decode_sector
stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S');private=WORK/'private';private.mkdir(exist_ok=True)
spec=importlib.util.spec_from_file_location('hardware_test',WORK/'test-pico-bridge-v042.py');base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
packets=[];frames=[];snapshot={}
class TraceSocket:
    def __init__(self,inner):self.inner=inner
    def __getattr__(self,k):return getattr(self.inner,k)
    def sendto(self,data,peer):
        result=self.inner.sendto(data,peer);packets.append(dict(direction='tx',at=time.perf_counter(),peer=list(peer),hex=data.hex()));return result
    def recvfrom(self,*args):
        data,peer=self.inner.recvfrom(*args);packets.append(dict(direction='rx',at=time.perf_counter(),peer=list(peer),hex=data.hex()));return data,peer
class RecordedClient(Client):
    def __init__(self,*args,**kwargs):super().__init__(*args,**kwargs);self.sock=TraceSocket(self.sock)
    def poll(self,*args,**kwargs):
        f=super().poll(*args,**kwargs)
        if f:
            frames.append(dict(flags=f['flags'],boot=f['boot'],source_us=f['source_us'],received_at=f['received_at'],rtt_ms=f['rtt_ms'],events=[dict(at_us=e['at_us'],sequence=e['sequence'],motors=e['motors'].hex()) for e in f['events']]))
        return f
base.Client=RecordedClient
def snapshot_before_end(m):
    m.send(0x80,b'\xfdSNAPLOG5');raw=m.read_range(0xa000,65536)
    decoded=decode_sector(raw);snapshot.update(decoded)
    (private/('ram-journal-'+stamp+'.bin')).write_bytes(raw)
    snapshot['raw_sha256']=hashlib.sha256(raw).hexdigest()
base.before_end=snapshot_before_end
code=1
try:code=base.main()
finally:
    packet_file=private/('ram-udp-original-'+stamp+'.json')
    packet_file.write_text(json.dumps(packets,indent=2),encoding='utf-8')
    received=[e for f in frames for e in f['events']]
    local=[e['motors_hex'] for e in snapshot.get('events',[]) if e['motors_hex'] is not None]
    checks=dict(original_test_passed=code==0,ram_snapshot_crc_valid=snapshot.get('crc_valid',False),
        local_log_complete=snapshot.get('complete',False),all_motor_fields_match=local==[e['motors'] for e in received] and bool(local),
        complete_sequence=[e['sequence'] for e in received]==list(range(len(received))),end_confirmed=base.report.get('terminal_ack_replied',False))
    report=dict(status='PASSED_COMPLETE_RAM_RECHECK' if all(checks.values()) else 'INCOMPLETE',checks=checks,
        motor_commands=0,persistent_writes=0,local_motor_fields=len(local),received_motor_fields=len(received),
        original_udp_packet_count=len(packets),original_udp_sha256=hashlib.sha256(packet_file.read_bytes()).hexdigest(),
        original_udp_location='local ignored work/private; contains live session nonce',
        local_ram_snapshot=snapshot,received_frames=frames,
        note='RAM snapshot is taken before stream end; END2 persistence still requires a separate Flash test. Original UDP packets are private; decoded events contain no session token.')
    path=ROOT/'docs'/('WINDOWS_RAM_CAPTURE_RECHECK_'+stamp+'.json');path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('local_ram_snapshot','received_frames')},indent=2));print(str(path))
raise SystemExit(0 if all(checks.values()) else 1)
