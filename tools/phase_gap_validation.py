"""Pure integrity checks for final, producer-idle phase snapshots."""
import json,math

def assess_phase_gap(child):
    diagnostics=child.get('transport_diagnostics',{});d=diagnostics.get('phase_gap',{})
    checks={}
    try:
        checks.update(healthy=d.get('healthy') is True and d.get('errors')==0 and d.get('fault_latched') is False,
            atomic_detail=d.get('snapshot_atomic') is True,producer_idle=d.get('in_flight') is None,
            bounded=d.get('max_events')==65536 and type(d.get('recorded_events')) is int and 0<d['recorded_events']<=65536,
            completed_counts=d['recorded_events']==d['poll_calls']+d['pause_calls'],
            old_counts_match=d['poll_calls']==diagnostics['poll_calls'] and d['frames']==diagnostics['responses'] and d['timeouts']==diagnostics['timeouts'],
            no_producer_errors=d['poll_errors']==0 and d['pause_errors']==0,
            metadata_only=d.get('packet_bytes_recorded') is False and d.get('session_or_peer_recorded') is False,
            finite_cost=all(type(d.get(k)) in (int,float) and math.isfinite(d[k]) and d[k]>=0 for k in ('maximum_finish_observer_seconds','maximum_begin_observer_seconds','snapshot_copy_seconds')),
            shape=d['ring_capacity']==128 and d['context_capacity']==8 and d['pre_rows']==16 and d['post_rows']==8,
            capacity=len(d['recent_events'])<=128 and len(d['contexts'])<=8,
            compact_bytes=len(json.dumps(d,separators=(',',':'),allow_nan=False).encode('utf-8'))<=262144)
        contexts=d['contexts'];maximum=d['maximum_receive_gap'];anchor=maximum['row'];prior=maximum['previous_frame']
        checks['maximum_matches_counter']=math.isclose(anchor['receive_gap_seconds'],diagnostics['maximum_response_gap_seconds'],rel_tol=0,abs_tol=1e-9)
        checks['maximum_has_original_predecessor']=prior['event_index']<anchor['event_index'] and math.isclose(anchor['received_at']-prior['received_at'],anchor['receive_gap_seconds'],rel_tol=0,abs_tol=1e-9)
        checks['maximum_context_retained']=d['protected_gap_event_index']==anchor['event_index'] and any(c['anchor']==anchor for c in contexts)
        def valid(row):
            return (type(row['event_index']) is int and 1<=row['event_index']<=d['recorded_events'] and row['phase'] in ('poll','pause')
                and all(type(row[k]) in (int,float) and math.isfinite(row[k]) for k in ('start','end','duration_seconds'))
                and row['end']>=row['start'] and math.isclose(row['end']-row['start'],row['duration_seconds'],rel_tol=0,abs_tol=1e-9))
        checks['row_integrity']=all(valid(r) for r in d['recent_events']) and all(valid(r) for c in contexts for r in c['pre']+[c['anchor']]+c['post'])
        checks['context_integrity']=all(len(c['pre'])<=16 and len(c['post'])<=8 and c['pre_complete']==(len(c['pre'])==16) and c['post_complete']==(len(c['post'])==8)
            and all(a['event_index']<b['event_index'] for a,b in zip(c['pre']+[c['anchor']]+c['post'],(c['pre']+[c['anchor']]+c['post'])[1:])) for c in contexts)
    except (KeyError,TypeError,ValueError,OverflowError):checks['required_fields_and_types']=False
    return dict(passed=bool(checks) and all(checks.values()),checks=checks,
        scope='Integrity of recorded wrapper poll/pause spans and bounded contexts; not proof of a network root cause or improved latency.')
