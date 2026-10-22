import struct,zlib,json
from bridge_runtime import unpack,Renderer,BridgeFault
checks=[]
def check(name,ok):checks.append(dict(name=name,passed=bool(ok)));assert ok,name
def fault(call):
    try:call()
    except BridgeFault:return True
    return False
def packet(flags=7,dropped=0):
    b=struct.pack('<4sBBHQIIIHH',b'BHR2',2,flags,52,123,7,4,10000,1,dropped)
    b+=struct.pack('<II8s',9000,0,bytes.fromhex('0001404000014040'))
    return b+struct.pack('<I',zlib.crc32(b))
check('wire_roundtrip',unpack(packet(),123,7)['events'][0]['at_us']==9000)
bad=bytearray(packet());bad[40]^=1
check('CRC_corruption_stops',fault(lambda:unpack(bad,123,7)))
check('wrong_session_stops',fault(lambda:unpack(packet(),124,7)))
check('wrong_request_stops',fault(lambda:unpack(packet(),123,8)))
check('source_overflow_stops',fault(lambda:unpack(packet(dropped=1),123,7)))
check('unknown_wire_flags_stop',fault(lambda:unpack(packet(flags=15),123,7)))
def frame(at=0,received=0,events=(),flags=7):return dict(source_us=at,received_at=received,events=list(events),flags=flags)
def event(raw,at=0):return dict(at_us=at,motors=bytes.fromhex(raw))
r=Renderer();r.feed(frame(events=[event('0001404000014040')]))
check('neutral_render',r.block(.064)==[[128]*8,[128]*8])
r.feed(frame(8000,.008,[event('801860b200000000',8000)]))
block=r.block(.072)
check('all_groups_preserved_with_stop',any(v!=128 for v in block[0]) and block[0][-3:]==[128]*3 and block[1]==[128]*8)
check('waveform_limit',all(abs(v-128)<=5 for side in block for v in side))
check('heartbeat_timeout_latches',fault(lambda:r.block(.100)) and bool(r.fault))
check('fault_does_not_autoresume',fault(lambda:r.feed(frame(110000,.11))))
r=Renderer();r.feed(frame());check('upstream_loss_stops',fault(lambda:r.feed(frame(flags=1))))
r=Renderer();check('old_active_sample_stops',fault(lambda:r.feed(frame(1000000,1,[event('801860b200000000')]))))
word=(1<<30)|(127<<9)|(127<<2)|(64<<16)
raw=(word.to_bytes(4,'little')+bytes.fromhex('00014040')).hex()
r=Renderer();check('unrenderable_frequency_stops',fault(lambda:r.feed(frame(events=[event(raw)]))))
word=(1<<30)|(127<<23)|(64<<16)|(64<<2)
raw=(word.to_bytes(4,'little')+bytes.fromhex('00014040')).hex()
r=Renderer();r.feed(frame(events=[event(raw)]));tripped=False
for i in range(8):
    now=.064+i*.008
    r.feed(frame(round(now*1e6),now))
    if fault(lambda:r.block(now)):tripped=True;break
check('sustained_energy_stops',tripped)
r=Renderer();r.feed(frame(events=[event('0001404000014040')]));r.block(.064)
check('already_sent_active_samples_stop',fault(lambda:r.feed(frame(1000,.065,[event('801860b200000000',1000)]))))
r=Renderer();r.feed(frame());r.block(0)
check('skipped_output_clock_stops',fault(lambda:r.block(.009)))
r=Renderer();f=frame(events=[event('801860b200000000')]);f['processed_at']=.100
check('queued_active_frame_processing_deadline',fault(lambda:r.feed(f)))
print(json.dumps(checks,indent=2))
