"""Conservative queue bound from archived serial producer spans; no hardware."""
import math
from analyse_recovered52_heartbeat import rows_from

def bound(earliest_drain,end,rows):
    if not all(math.isfinite(v) for v in (earliest_drain,end)) or end<=earliest_drain:raise ValueError('Invalid window')
    ordered=sorted(rows,key=lambda r:r['event_index'])
    left=[r for r in ordered if r['start']<=earliest_drain];right=[r for r in ordered if r['end']>=end]
    if not left or not right:raise ValueError('Missing producer window')
    first=left[-1]['event_index'];last=right[0]['event_index'];span=[r for r in ordered if first<=r['event_index']<=last]
    ids=[r['event_index'] for r in span]
    complete=ids==list(range(first,last+1)) and span[0]['start']<=earliest_drain and span[-1]['end']>=end
    if not complete:raise ValueError('Incomplete producer context; no queue bound claimed')
    ordered=span
    if any(b['start']<a['end']-1e-9 for a,b in zip(ordered,ordered[1:])):raise ValueError('Overlapping serial producer phases')
    candidates=[]
    for i,r in enumerate(ordered):
        if r.get('outcome')!='frame':continue
        if r['end']>=end:continue # validated poll has not returned to publish yet
        following=ordered[i+1] if i+1<len(ordered) else None
        if following is None or following['event_index']!=r['event_index']+1 or following['phase']!='pause':raise ValueError('Missing post-publication boundary')
        latest=following['start']
        if latest<=earliest_drain:continue
        if r['flags']&16:raise ValueError('Terminal dual-publication semantics need separate model')
        candidates.append(dict(event_index=r['event_index'],earliest_publication=r['end'],latest_publication=latest,motor_events=r['event_count']))
    return dict(earliest_possible_drain=earliest_drain,end=end,maximum_new_frames=len(candidates),maximum_new_motor_events=sum(r['motor_events'] for r in candidates),candidates=candidates,context_complete=True,actual_queue_depth_measured=False,actual_consumed_frame_count_unknown=True,assumptions=['Single serial collector producer and single consumer','collect_frames publishes a normal frame after poll returns and before pause starts','Original main loop drains FIFO before each dispatch check','Earliest drain bound is previous iteration completion, not an invented exact drain timestamp'])

def analyse_document(program):
    child=program['child'];context=child['dispatch_io']['first_fault']['context']
    if len(context)<3:raise ValueError('Need three main iteration rows')
    first=context[-3]['end'];last=context[-1]['start'];detail=child['transport_at_output_fault']['phase_gap']
    if not detail['snapshot_atomic']:raise ValueError('Non-atomic producer detail')
    return bound(first,last,list(rows_from(detail).values()))
