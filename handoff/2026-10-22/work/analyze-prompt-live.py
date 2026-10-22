"""Reconcile stored Pico data, actual prompt output and separately recorded feedback."""
import pathlib,json,argparse
from switch_hd_decode import Decoder
p=argparse.ArgumentParser();p.add_argument('capture',type=pathlib.Path);p.add_argument('live',type=pathlib.Path);p.add_argument('feedback',type=pathlib.Path);p.add_argument('--output',type=pathlib.Path,required=True);a=p.parse_args()
log=json.loads(a.capture.read_text(encoding='utf-8-sig'))['newest'];live=json.loads(a.live.read_text(encoding='utf-8'));child=live['child'];feedback=json.loads(a.feedback.read_text(encoding='utf-8'))
if feedback['live_report']!=a.live.name:raise ValueError('Feedback does not match live run')
local=[e['motors_hex'] for e in log['events'] if e['motors_hex'] is not None];wire=[e['motors'] for e in child['events']]
def active_groups(fields):
    decoders=[Decoder(),Decoder()];active=[]
    for index,field in enumerate(fields):
        raw=bytes.fromhex(field)
        for side in (0,1):
            for group,sample in enumerate(decoders[side].decode(raw[side*4:side*4+4])['samples']):
                if sample['low_amplitude'] or sample['high_amplitude']:active.append(dict(event=index,side=side,group=group,**sample))
    return active
active_local=active_groups(local);active_wire=active_groups(wire)
checks=dict(actual_switch_test=live['actual_switch_live_test'],local_log_complete=log['crc_valid'] and log['complete'] and not log['dropped_events'],
    received_fields_match_prefix=wire==local[:len(wire)],wire_sequences_contiguous=[e['sequence'] for e in child['events']]==list(range(len(wire))),
    all_active_groups_received=active_local==active_wire and len(active_wire)==2,
    selected_prompt_mode=child['prompt_ms']==120 and child['prompt_offset']==12,
    both_prompts_complete=child['prompt_counts']==[1,1] and child['active_samples']==[120,120],
    bounded_output=child['maximum_offset']<=12,
    both_processes_disabled=child['runtime_disable_ack'] and live['runtime_disable_ack'],
    original_configuration_unchanged=live['configuration_unchanged'],
    human_confirmed=feedback['felt_rumble'] and feedback['both_sides_felt'])
result=dict(passed_limited_perceptible_prompt_test=all(checks.values()),checks=checks,
    local_motor_fields=len(local),received_motor_fields=len(wire),all_fields_received=local==wire,
    final_unreceived_fields=local[len(wire):] if wire==local[:len(wire)] else None,
    active_groups=active_wire,rendered_samples=child['active_samples'],actual_maximum_offset=child['maximum_offset'],
    limitation='Calibrated 120ms notifications at fixed left160/right320Hz; not faithful Nintendo waveform reconstruction or full gameplay validation. Any missing neutral tail fields at timed shutdown remain reported separately.')
a.output.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))
raise SystemExit(0 if result['passed_limited_perceptible_prompt_test'] else 1)
