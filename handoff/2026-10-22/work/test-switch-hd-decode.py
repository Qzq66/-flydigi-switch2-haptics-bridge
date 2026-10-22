"""Protocol fixtures for offline HD rumble; all formats plus missing-state safety."""
from switch_hd_decode import Decoder
import math,json
checks=[]
def check(name,ok):
    checks.append({'name':name,'passed':bool(ok)})
    assert ok,name
def packed(kind,fields):
    w=kind<<30
    for offset,value in fields:w|=value<<offset
    return w.to_bytes(4,'little')
d=Decoder();r=d.decode(bytes.fromhex('00014040'))
check('neutral_absolute_7bit',r['format']=='one_7bit' and r['samples']==[dict(low_amplitude=0.0,low_hz=160.0,high_amplitude=0.0,high_hz=320.0,state_complete=True)])
check('zero_packet_preserves_state',d.decode(b'\0'*4)['samples']==[] and d.state==[-8,0,-8,0])
r=d.decode(packed(1,[(20,1),(25,1)]))
check('one_5bit_full_amplitude',r['samples'][0]['low_amplitude']==r['samples'][0]['high_amplitude']==1)
r=d.decode(packed(2,[(20,3),(25,3),(10,18),(15,30)]))
check('two_5bit_state_progression',len(r['samples'])==2 and r['samples'][0]['low_amplitude']==.5 and math.isclose(r['samples'][1]['low_amplitude'],2**-1.125) and math.isclose(r['samples'][1]['high_amplitude'],2**-.875))
r=d.decode(packed(2,[(0,1),(1,64),(23,127),(18,0),(8,0),(13,0)]))
check('two_7bit_select_high',r['format']=='two_7bit' and r['samples'][0]['high_amplitude']==1 and r['samples'][0]['high_hz']==320 and r['samples'][1]['high_amplitude']==0)
r=d.decode(packed(3,[(20,1),(25,1),(10,0),(15,0),(0,1),(5,1)]))
check('three_5bit_reset_and_restore',[s['low_amplitude'] for s in r['samples']]==[1,0,1])
r=d.decode(packed(1,[(1,1),(23,127),(13,0),(18,0),(3,1),(8,1)]))
check('three_7bit_select_low_amplitude',r['format']=='three_7bit' and [s['low_amplitude'] for s in r['samples']]==[1,0,1])
d.invalidate();r=d.decode(packed(1,[(20,24),(25,24)]))
check('delta_after_gap_stays_unknown',not r['samples'][0]['state_complete'] and all(r['samples'][0][k] is None for k in ('low_amplitude','low_hz','high_amplitude','high_hz')))
r=d.decode(bytes.fromhex('00014040'))
check('absolute_recovers_after_gap',r['samples'][0]['state_complete'])
check('captured_left_packet_is_three_sample',d.decode(bytes.fromhex('c2000f40'))['format']=='three_7bit')
check('captured_right_packet_is_three_sample',d.decode(bytes.fromhex('c318606d'))['format']=='three_7bit')
try:d.decode(b'\0');bad=False
except ValueError:bad=True
check('truncated_motor_word_rejected',bad)
print(json.dumps(checks,indent=2))
