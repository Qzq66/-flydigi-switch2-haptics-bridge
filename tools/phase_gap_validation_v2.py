"""Validate retained RTT split arithmetic as well as original bounded context."""
import math
from phase_gap_validation import assess_phase_gap as previous_assess

def assess_phase_gap(child):
    result=previous_assess(child);checks=dict(result['checks'])
    try:
        d=child['transport_diagnostics']['phase_gap']
        checks['rtt_schema_version']=d['version']==2
        rows=list(d['recent_events'])
        for c in d['contexts']:rows+=c['pre']+[c['anchor']]+c['post']
        rows += [d['maximum_receive_gap']['row'],d['maximum_receive_gap']['previous_frame'],d['maximum_poll']]
        count=0
        for r in rows:
            if r['phase']!='poll' or r['outcome']!='frame':continue
            count+=1
            a,b,c=[r[k] for k in ('poll_start_to_transport_timer_seconds','transport_receive_decode_seconds','received_to_poll_end_seconds')]
            if not all(type(v) in (int,float) and math.isfinite(v) and v>=0 for v in (a,b,c)):raise ValueError('Invalid RTT components')
            if not math.isclose(a+b,r['received_at']-r['start'],rel_tol=0,abs_tol=1e-9):raise ValueError('Pre-receive components differ')
            if not math.isclose(c,r['end']-r['received_at'],rel_tol=0,abs_tol=1e-9):raise ValueError('Post-receive component differs')
        checks['retained_rtt_components_valid']=count>0
    except (KeyError,TypeError,ValueError,OverflowError):checks['retained_rtt_components_valid']=False
    return dict(passed=bool(checks) and all(checks.values()),checks=checks,scope='Host poll/after-send receive-decode timing; not radio-only or one-way latency.')
