"""Offline captured-wire simulation, no HID or network access."""
import json,pathlib,math
from bridge_runtime import Renderer
root=pathlib.Path(__file__).absolute().parent.parent
source=root/'outputs/flydigi-live-bench-child-20261022-155010.json'
events=json.loads(source.read_text(encoding='utf-8'))['events'];r=Renderer(prompt_ms=120)
index=0;flags=3;maximum=0;frames=0
for i in range(math.ceil(events[-1]['at_us']/8000)+30):
    source_at=i*.008;received=source_at+.010;ready=[]
    while index<len(events) and events[index]['at_us']<=round(source_at*1e6):
        e=events[index];ready.append(dict(at_us=e['at_us'],sequence=e['sequence'],motors=bytes.fromhex(e['motors'])));flags=e['flags'];index+=1
    r.feed(dict(source_us=round(source_at*1e6),received_at=received,processed_at=received,events=ready,flags=flags))
    if received>=.074-1e-9:
        block=r.block(.074+frames*.008);frames+=1
        maximum=max(maximum,max(abs(v-128) for side in block for v in side))
assert index==303 and r.active_total==[120,120] and r.prompt_counts==[1,1] and maximum<=3
result=dict(passed=True,source=source.name,raw_events=index,source_active_samples=r.source_active_total,
    rendered_active_samples=r.active_total,prompt_counts=r.prompt_counts,maximum_offset=maximum,
    transport='offline synthetic fixed 10ms reception offset; not measured network latency',physical_output=False)
(root/'outputs/bridge-v041-captured-prompt-simulation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
