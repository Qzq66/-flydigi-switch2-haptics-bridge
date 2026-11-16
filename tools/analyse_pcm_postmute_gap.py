"""Read-only post-mute timing analysis, respecting bounded and non-atomic snapshots."""
import hashlib,json,math,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1]

def decompose(rows,heartbeat=.080):
    frames=[i for i,r in enumerate(rows) if r['kind']=='frame' and r.get('gap') is not None]
    if not frames:return dict(available=False,reason='No retained receive gap')
    i=max(frames,key=lambda n:rows[n]['gap']);later=rows[i]
    previous=[n for n in range(i) if rows[n]['kind']=='frame']
    if not previous:return dict(available=False,reason='Original preceding receive not retained')
    j=previous[-1];earlier=rows[j];gap=later['at']-earlier['at']
    if not math.isclose(gap,later['gap'],rel_tol=0,abs_tol=1e-6):return dict(available=False,reason='Retained neighbour is not original adjacent receive')
    middle=rows[j+1:i]
    if len(middle)!=1 or middle[0]['kind']!='timeout':return dict(available=False,reason='Not a single-timeout interval')
    timeout=middle[0];timeout_start=timeout['at']-timeout['duration']
    # Frame.at is inside Client.poll; duration ends after Client.poll returns.
    # Therefore frame.at-duration is a LOWER bound for that poll's start.
    next_start_lower=later['at']-later['duration']
    if timeout_start<earlier['at'] or next_start_lower<timeout['at']:return dict(available=False,reason='Interval ordering inconsistent')
    return dict(available=True,receive_gap_ms=gap*1000,previous_frame_at=earlier['at'],timeout_end_at=timeout['at'],later_frame_at=later['at'],
        before_timeout_poll_ms=(timeout_start-earlier['at'])*1000,timeout_poll_ms=timeout['duration']*1000,
        timeout_end_to_next_receive_ms=(later['at']-timeout['at'])*1000,next_poll_duration_ms=later['duration']*1000,
        post_timeout_to_next_poll_start_lower_ms=(next_start_lower-timeout['at'])*1000,
        heartbeat_margin_at_timeout_return_ms=(earlier['at']+heartbeat-timeout['at'])*1000,
        next_poll_start_beyond_heartbeat_deadline_lower_ms=(next_start_lower-earlier['at']-heartbeat)*1000,
        accepted_board_timestamp_gap_ms=((later['source_us']-earlier['source_us'])&0xffffffff)/1000,
        board_and_pc_absolute_clocks_synchronised=False,
        lower_bound_is_not_measured_sleep=True,request_ids_and_send_times_retained=False)

def window(snapshot):
    rows=snapshot['recent']
    if not rows or any(not math.isfinite(r['at']) or not math.isfinite(r['duration']) or r['duration']<0 for r in rows):raise ValueError('Invalid observed interval')
    if any(b['at']<a['at'] for a,b in zip(rows,rows[1:])):raise ValueError('Observation time reversed')
    return dict(rows=len(rows),first_at=rows[0]['at'],last_at=rows[-1]['at'],duration_seconds=rows[-1]['at']-rows[0]['at'],
        timeout_rows=sum(r['kind']=='timeout' for r in rows),error_rows=sum(r['kind']=='error' for r in rows),
        retained_max_gap_ms=max((r.get('gap') or 0)*1000 for r in rows),counter_max_gap_ms=snapshot['maximum_response_gap_seconds']*1000,
        calls_minus_responses_and_timeouts=snapshot['poll_calls']-snapshot['responses']-snapshot['timeouts'],
        snapshots_are_atomic=False,observed_boot_count=len(snapshot['observed_boot_ids']))

def main():
    frozen=ROOT/'docs/FIDELITY_PCM_RUN_FREEZE_20261027-221627.json'
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    for row in json.loads(frozen.read_text())['files']:
        if digest(ROOT/row['path'])!=row['sha256']:raise ValueError('Frozen runtime source/evidence changed')
    source=ROOT/'docs/FIDELITY_GAME_RUN_20261027-221627.json';r=json.loads(source.read_text());c=r['child']
    plan=json.loads((ROOT/'docs/FIDELITY_PCM_PLAN_G41_2026-10-27.json').read_text())
    if digest(ROOT/'tools/game_transport_diagnostics.py')!=plan['tool_sha256']['game_transport_diagnostics.py']:raise ValueError('Observer source binding')
    if digest(ROOT/'handoff/2026-10-22/work/bridge_transport.py')!=plan['transport_sha256']['bridge_transport.py']:raise ValueError('Transport source binding')
    if r['status']!='INCOMPLETE' or c['output_fault']!="BridgeFault('wire heartbeat timeout')":raise ValueError('Expected preserved failure')
    first=c['transport_at_output_fault'];last=c['transport_diagnostics'];fw=window(first);lw=window(last)
    detail=decompose(first['recent']);reported_max=last['maximum_response_gap_seconds']*1000
    max_in_either=any(math.isclose((x.get('gap') or 0)*1000,reported_max,rel_tol=0,abs_tol=1e-6) for s in (first,last) for x in s['recent'])
    checks=dict(fault_preserved=True,stopped_at_fault=c['output_at_fault']['stop_confirmed'] is True,
        no_generated_frames_after_fault=c['output_at_fault']['frames']==c['output_frames']==c['written_pcm']['recorded_frames'],
        first_gap_original_adjacent_and_decomposed=detail['available'],no_snapshot_overlap=fw['last_at']<lw['first_at'],
        global_larger_gap_not_in_retained_rows=not max_in_either and reported_max>fw['counter_max_gap_ms'])
    if not all(checks.values()):raise ValueError('Unexpected snapshot coverage; retain as incomplete analysis')
    result=dict(status='COMPLETED_READONLY_POSTMUTE_GAP_ANALYSIS_NOT_GAME_PASS',hardware_access=False,motor_commands=0,checks=checks,
        source_report_sha256=digest(source),runtime_freeze_sha256=digest(frozen),ring_capacity=64,
        fault_snapshot_window=fw,final_snapshot_window=lw,first_gap=detail,
        between_retained_windows_seconds=lw['first_at']-fw['last_at'],whole_run_max_gap_ms=reported_max,
        whole_run_max_gap_exact_event_retained=max_in_either,whole_run_max_gap_root_cause_known=False,
        root_cause_of_first_gap_proven=False,poll_timeout_seconds_in_accepted_transport=.060,requested_collector_pause_seconds=.004,
        stopped_at_pc_clock=c['stopped_at_pc_clock'],last_fault_snapshot_transport_event_after_stop_seconds=fw['last_at']-c['stopped_at_pc_clock'],
        snapshot_counter_residual_is_not_packet_loss=True,
        limitations=['Only accepted replies and 64 recent poll results are retained, not raw UDP requests/replies.',
        'Timeout call duration includes input read/send/receive/scheduling, not pure radio latency.',
        'Post-timeout bound includes observer bookkeeping, requested sleep and thread scheduling; sleep itself was not timed.',
        'Board timestamp spacing between accepted replies cannot locate missing/discarded old replies.',
        'Fault snapshot is not atomic; count residual may represent an in-flight poll.',
        'No new output, threshold changes, firmware writes or physical fidelity validation.'])
    out=ROOT/'docs/PCM_POSTMUTE_GAP_ANALYSIS_2026-10-27.json'
    with out.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps(result,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
