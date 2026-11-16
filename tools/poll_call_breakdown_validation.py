"""Validate final idle host-call summaries; no packet or hardware API."""
import json,math

def assess_breakdown(child):
    d=child.get('poll_call_breakdown',{});checks={}
    try:
        checks.update(healthy=d['healthy'] is True and d['errors']==0,idle=d['in_flight'] is None,
            counts=0<d['poll_calls']<=32768 and d['poll_calls']==child['transport_diagnostics']['poll_calls'],
            bounds=d['limits']==dict(polls=32768,calls_per_poll=8,recent=64,slow=16) and len(d['recent'])<=64 and len(d['slowest'])<=16,
            metadata_only=d['packet_or_peer_or_session_recorded'] is False,
            compact_size=len(json.dumps(d,separators=(',',':'),allow_nan=False).encode())<=262144)
        rows=d['recent']+d['slowest'];m=d['maximum_receive_gap']
        if m:rows += [m['row'],m['previous_frame']]
        good=bool(rows)
        for r in rows:
            good &= type(r['poll_index']) is int and 1<=r['poll_index']<=d['poll_calls'] and len(r['calls'])<=8
            good &= r['outcome'] in ('frame','timeout') and math.isclose(r['end']-r['start'],r['duration_seconds'],abs_tol=1e-9,rel_tol=0)
            prev=r['start']
            for c in r['calls']:
                good &= c['kind'] in ('input_read','sendto','recvfrom') and all(type(c[k]) in (int,float) and math.isfinite(c[k]) for k in ('start','end','duration_seconds'))
                good &= prev<=c['start']<=c['end']<=r['end'] and math.isclose(c['end']-c['start'],c['duration_seconds'],abs_tol=1e-9,rel_tol=0)
                prev=c['end']
        checks['ordered_call_intervals']=bool(good)
    except (KeyError,TypeError,ValueError,OverflowError):checks['required_shape']=False
    return dict(passed=bool(checks) and all(checks.values()),checks=checks)
