"""Safety and timing checks for the explicit calibrated notification mapping."""
import json
from bridge_runtime import Renderer,BridgeFault
checks=[]
def check(name,ok):checks.append(dict(name=name,passed=bool(ok)));assert ok,name
def frame(now,events=(),flags=7):return dict(source_us=round(now*1e6),received_at=now,processed_at=now,events=list(events),flags=flags)
def event(raw,at=0):return dict(at_us=at,motors=bytes.fromhex(raw))
def init():
    r=Renderer(prompt_ms=120);r.feed(frame(0,[event('0001404000014040'),event('801860b200000000')]))
    return r
def fault(fn):
    try:fn()
    except BridgeFault:return True
    return False
r=init();pcm=[[],[]]
for i in range(20):
    now=.064+i*.008;r.feed(frame(now));b=r.block(now)
    for s in (0,1):pcm[s]+=b[s]
check('one_source_group_becomes_exactly_120_samples',r.active_total==[120,0] and r.source_active_total==[5,0])
check('calibrated_amplitude_and_other_side_neutral',max(abs(v-128) for v in pcm[0])==3 and all(v==128 for v in pcm[1]))
check('automatic_neutral_after_prompt',pcm[0][-40:]==[128]*40)
check('prompt_is_not_retriggered_by_empty_heartbeats',r.prompt_counts==[1,0])
r=init();r.block(.064)
check('heartbeat_loss_cancels_longer_prompt',fault(lambda:r.block(.152)) and r.prompt_remaining==[0,0])
check('fault_cannot_resume_prompt',fault(lambda:r.feed(frame(.153))))
r=init();r.block(.064);r.feed(frame(.072,flags=3))
check('vibration_disable_cancels_prompt_immediately',r.block(.072)==[[128]*8,[128]*8] and r.prompt_remaining==[0,0])
r.feed(frame(.080,flags=7))
check('reenable_without_new_active_event_does_not_resume_old_prompt',r.block(.080)==[[128]*8,[128]*8] and r.prompt_counts==[1,0])
r=init();r.block(.064)
check('USB_loss_cancels_prompt',fault(lambda:r.feed(frame(.072,flags=1))) and r.prompt_remaining==[0,0])
r=Renderer(prompt_ms=120);r.feed(frame(0,[event('0001404000014040')]))
left=[];right=[]
for i in range(40):
    now=.064+i*.008;ev=[]
    if i==0:ev=[event('801860b200000000')]
    if i==11:ev=[event('00000000c318606d',88000)]
    r.feed(frame(now,ev));a,b=r.block(now);left+=a;right+=b
check('left_right_start_order_and_independent_duration',r.active_total==[120,120] and min(i for i,v in enumerate(left) if v!=128)<min(i for i,v in enumerate(right) if v!=128))
r=init()
for i in range(20):
    now=.064+i*.008
    r.feed(frame(now,[event('801860b200000000',32000)] if i==4 else []));r.block(now)
check('overlapping_source_pulse_does_not_extend_output',r.active_total==[120,0] and r.prompt_counts==[1,0])
r=Renderer(prompt_ms=120);r.feed(frame(0,[event('0001404000014040')]))
tripped=False
for i in range(100):
    now=.064+i*.008;ev=[event('801860b200000000',int(i*.008*1e6))] if i in (0,25,50,75) else []
    r.feed(frame(now,ev))
    if fault(lambda:r.block(now)):tripped=True;break
check('fourth_prompt_is_rejected',tripped and r.prompt_counts==[3,0])
check('all_supported_values_are_explicit',Renderer().prompt_ms==0)
try:Renderer(prompt_ms=121);invalid=False
except ValueError:invalid=True
check('unreviewed_duration_rejected',invalid)
r=Renderer(prompt_ms=120,prompt_offset=12);r.feed(frame(0,[event('0001404000014040'),event('801860b200000000')]))
pcm=[]
for i in range(20):
    now=.064+i*.008;r.feed(frame(now));pcm+=r.block(now)[0]
check('explicit_higher_amplitude_retains_120ms_cap',r.active_total==[120,0] and max(abs(v-128) for v in pcm)==12)
try:Renderer(prompt_ms=120,prompt_offset=13);invalid=False
except ValueError:invalid=True
check('unreviewed_amplitude_rejected',invalid)
print(json.dumps(checks,indent=2))
