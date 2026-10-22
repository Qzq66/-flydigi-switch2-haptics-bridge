"""Compare actual wireless receiver events with independently retained Pico log."""
import argparse,pathlib,json,statistics
from switch_hd_decode import Decoder
p=argparse.ArgumentParser();p.add_argument('capture',type=pathlib.Path);p.add_argument('live',type=pathlib.Path);p.add_argument('--output',type=pathlib.Path,required=True);p.add_argument('--human-feedback',type=pathlib.Path,required=True);a=p.parse_args()
feedback=json.loads(a.human_feedback.read_text(encoding='utf-8'))
if feedback['live_report']!=a.live.name:raise ValueError('Human feedback belongs to another run')
capture=json.loads(a.capture.read_text(encoding='utf-8-sig'))['newest']
live=json.loads(a.live.read_text(encoding='utf-8-sig'));child=live['child']
local=[e for e in capture['events'] if e['motors_hex'] is not None];wire=child['events']
checks=dict(actual_switch_path=live['actual_switch_live_test'],local_log_crc_valid=capture['crc_valid'],
    local_capture_complete=capture['complete'] and capture['dropped_events']==0,
    all_raw_motor_fields_equal=[e['motors_hex'] for e in local]==[e['motors'] for e in wire],
    wire_sequence_complete=[e['sequence'] for e in wire]==list(range(len(wire))),
    both_sides_rendered=all(child['active_samples']),bounded_waveform=child['maximum_offset']<=5,
    parent_and_child_disabled=live['runtime_disable_ack'] and child['runtime_disable_ack'],
    configuration_unchanged=live['configuration_unchanged'])
offsets=[w['at_us']-l['at_us'] for w,l in zip(wire,local)]
decoders=[Decoder(),Decoder()];active=[]
for e in wire:
    raw=bytes.fromhex(e['motors'])
    for side in (0,1):
        for i,s in enumerate(decoders[side].decode(raw[side*4:side*4+4])['samples']):
            if s['low_amplitude'] or s['high_amplitude']:active.append(dict(sequence=e['sequence'],side=side,group=i,**s))
result=dict(checks=checks,passed=all(checks.values()),local_motor_fields=len(local),wire_motor_fields=len(wire),
    received_source_clock_origin_difference_us=dict(min=min(offsets),max=max(offsets),median=statistics.median(offsets)),
    active_groups=active,rendered_active_samples=child['active_samples'],nonneutral_frames=child['nonneutral_frames'],
    actual_maximum_offset=child['maximum_offset'],human_felt_rumble=feedback['felt_rumble'],
    limitation='Human reported icon but no felt rumble. First-test rendering uses experimental 5ms groups and a 64ms buffer; this does not verify physical fidelity or end-to-end actuator latency.')
a.output.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))
raise SystemExit(0 if result['passed'] else 1)
