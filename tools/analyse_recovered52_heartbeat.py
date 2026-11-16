"""Pure phase-span reconstruction; no hardware, no inferred one-way delays."""
import math

def rows_from(detail):
    rows={}
    candidates=list(detail['recent_events'])
    for c in detail['contexts']:candidates+=c['pre']+[c['anchor']]+c['post']
    for key in ('maximum_poll','maximum_actual_pause'):
        if detail.get(key):candidates.append(detail[key])
    if detail.get('maximum_receive_gap'):
        candidates += [detail['maximum_receive_gap']['row'],detail['maximum_receive_gap']['previous_frame']]
    for r in candidates:
        i=r['event_index']
        if i in rows and rows[i]!=r:raise ValueError('Conflicting phase copies')
        if not all(type(r[k]) in (float,int) and math.isfinite(r[k]) for k in ('start','end','duration_seconds')) or r['end']<r['start']:raise ValueError('Invalid phase time')
        if not math.isclose(r['end']-r['start'],r['duration_seconds'],abs_tol=1e-9,rel_tol=0):raise ValueError('Phase duration mismatch')
        rows[i]=r
    return rows

def span(rows,previous,later,heartbeat=.080):
    if not 0<heartbeat<1:raise ValueError('Heartbeat argument')
    a=previous['event_index'];b=later['event_index']
    if b<=a or previous['outcome']!='frame' or later['outcome']!='frame':raise ValueError('Frame bounds')
    gap=later['received_at']-previous['received_at']
    if gap<0 or not math.isclose(gap,later['receive_gap_seconds'],abs_tol=1e-9,rel_tol=0):raise ValueError('Receive gap mismatch')
    missing=[i for i in range(a+1,b+1) if i not in rows]
    selected=[rows[i] for i in range(a+1,b+1) if i in rows]
    if any(r['outcome']=='frame' for r in selected[:-1] if r['phase']=='poll'):raise ValueError('Not adjacent accepted frames')
    deadline=previous['received_at']+heartbeat
    return dict(receive_gap_seconds=gap,heartbeat_excess_seconds=max(0.,gap-heartbeat),
        previous_receive=previous['received_at'],next_receive=later['received_at'],heartbeat_deadline=deadline,
        complete_phase_span=not missing,missing_phase_indices=missing,
        observed_timeout_calls=sum(r['phase']=='poll' and r.get('outcome')=='timeout' for r in selected),
        observed_timeout_seconds=sum(r['duration_seconds'] for r in selected if r['phase']=='poll' and r.get('outcome')=='timeout'),
        observed_pause_seconds=sum(r['duration_seconds'] for r in selected if r['phase']=='pause'),
        next_poll_seconds=later['duration_seconds'],next_poll_start_relative_to_deadline=later['start']-deadline,
        source_interval_us=(later['source_us']-previous['source_us'])&0xffffffff,
        clocks_synchronised=False,poll_is_not_radio_only=True,rows=selected)
