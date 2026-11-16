"""Read-only cross-thread interval analysis, using only one child PC clock."""
import math
from analyse_recovered52_heartbeat import rows_from

def compare(start,end,rows):
    if not all(math.isfinite(v) for v in (start,end)) or end<=start:raise ValueError('Invalid outer gap')
    selected=sorted((r for r in rows if r['end']>start and r['start']<end),key=lambda r:r['event_index'])
    if not selected:raise ValueError('No collector context')
    ids=[r['event_index'] for r in selected]
    contiguous=ids==list(range(ids[0],ids[-1]+1))
    covered=0.;right=start;durations=dict(poll=0.,pause=0.);progress=[];frames=[]
    for r in selected:
        if r['phase'] not in durations or r['end']<r['start']:raise ValueError('Invalid collector phase')
        a=max(start,r['start']);b=min(end,r['end']);durations[r['phase']]+=b-a
        if b>right:covered+=b-max(a,right);right=b
        for name in ('start','end'):
            if start<r[name]<end:progress.append(dict(event_index=r['event_index'],boundary=name,at=r[name]))
        if r.get('outcome')=='frame' and start<=r['received_at']<=end:frames.append(dict(event_index=r['event_index'],at=r['received_at'],event_count=r['event_count'],flags=r['flags']))
    return dict(outer_gap_seconds=end-start,context_contiguous=contiguous,context_brackets_gap=selected[0]['start']<=start and selected[-1]['end']>=end,collector_phase_seconds=durations,collector_phase_coverage_seconds=covered,between_phase_seconds=max(0.,end-start-covered),collector_progress_boundaries=progress,accepted_frames_inside_gap=frames,collector_progress_observed=bool(progress),new_motor_events_in_accepted_frames=sum(f['event_count'] for f in frames),rows=selected,limitations=['Poll/pause spans include waiting; not CPU occupancy','Other-thread progress does not identify why output thread did not run','No attribution to disk, GIL or OS without corresponding stage records'])

def analyse_document(program):
    child=program['child'];fault=child['dispatch_io']['first_fault'];context=fault['context'];a=context[-2]['end'];b=context[-1]['start'];detail=child['transport_at_output_fault']['phase_gap']
    if not detail['snapshot_atomic']:raise ValueError('Atomic detail required')
    result=compare(a,b,list(rows_from(detail).values()));result.update(fault_lateness_ms=fault['lateness_seconds']*1000,scope='Same child PC perf_counter timelines; no PC-Pico clock alignment assumed',root_cause='unproven')
    return result
