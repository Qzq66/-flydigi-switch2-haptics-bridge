"""Independent source reconstruction compared with post-write PCM summaries."""
import hashlib,math
from audit_game_parameter_mapping import emitted_timelines
from haptic_fidelity_candidate import reconstruct
from written_pcm_probe import encode_report

def reference(child):
    timelines,start,end=emitted_timelines(child);r=reconstruct(timelines,start,end);left,right=r['pcm']
    wire=hashlib.sha256()
    for i in range(0,len(left),8):wire.update(encode_report(left[i:i+8],right[i:i+8]))
    return dict(recorded_frames=child['output_frames'],samples_per_side=len(left),left_sha256=hashlib.sha256(bytes(left)).hexdigest(),
        right_sha256=hashlib.sha256(bytes(right)).hexdigest(),report_sha256=wire.hexdigest(),
        squared_code_sum=[sum((v-128)**2 for v in side) for side in (left,right)],
        peak_per_side=[max(abs(v-128) for v in side) for side in (left,right)],
        nonneutral_samples=[sum(v!=128 for v in side) for side in (left,right)])

def assess_written(child):
    observed=child.get('written_pcm',{});expected=None;error=None
    try:expected=reference(child)
    except (ValueError,KeyError,TypeError,IndexError,OverflowError) as exc:error=type(exc).__name__
    checks=dict(complete=observed.get('complete') is True,
        observation_point=observed.get('observation_point')=='after_validated_writer_successful_return',
        bounded=observed.get('frame_limit')==1900 and type(observed.get('recorded_frames')) is int and 0<observed['recorded_frames']<=1900,
        no_errors=all(observed.get(k)==0 for k in ('write_failures','record_errors','rejected_before_write')) and all(observed.get(k) is False for k in ('fault_latched','possible_partial_or_unconfirmed_write')) and not observed.get('snapshot_error'),
        submission_only=observed.get('device_per_frame_ack') is False,
        all_successes_recorded=observed.get('attempts')==observed.get('writer_successes')==observed.get('recorded_frames'),
        finite_cost=all(type(observed.get(k)) in (int,float) and math.isfinite(observed[k]) and observed[k]>=0 for k in ('maximum_observer_seconds','maximum_writer_call_seconds')),
        reference_available=expected is not None)
    if expected is not None:
        for key,value in expected.items():checks[key]=observed.get(key)==value
    return dict(passed=all(checks.values()),checks=checks,reference_error=error,expected=expected,
        scope='Successful host writer submissions only; not controller receipt or mechanical execution.')
