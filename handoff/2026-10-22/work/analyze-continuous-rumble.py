"""Offline decoding and arrival timing; never generates physical output."""
import argparse,pathlib,json,statistics,collections
from switch_hd_decode import decode_capture
p=argparse.ArgumentParser();p.add_argument('capture',type=pathlib.Path);p.add_argument('--prefix',type=pathlib.Path,required=True)
a=p.parse_args();log=json.loads(a.capture.read_text(encoding='utf-8-sig'))['newest']
if log['version']!=5:raise ValueError('Requires continuous BPROLOG5')
decoded=decode_capture(a.capture);frames=[e for e in log['events'] if e['motors_hex'] is not None]
deltas=[b['at_us']-c['at_us'] for c,b in zip(frames,frames[1:])]
timeline=[];formats=collections.Counter();unknown=0
for packet in decoded['events']:
    for side in ('left','right'):
        output=packet[side];formats[output['format']]+=1
        for index,sample in enumerate(output['samples']):
            unknown+=not sample['state_complete']
            timeline.append(dict(received_at_us=packet['at_us'],side=side,
                sample_index_in_packet=index,**sample))
summary=dict(source=a.capture.name,complete=log['complete'],total_events=log['total_events'],
    stored_events=log['stored_events'],dropped_events=log['dropped_events'],
    event_sequence_contiguous=all(e['sequence']==i for i,e in enumerate(log['events'])),
    microsecond_timestamps_monotonic=all(b['at_us']>=c['at_us'] for c,b in zip(log['events'],log['events'][1:])),
    motor_packets=len(frames),decoded_samples=len(timeline),unknown_state_samples=unknown,formats=dict(formats),
    motor_arrival_intervals_us=dict(min=min(deltas),median=statistics.median(deltas),max=max(deltas)) if deltas else None,
    hardware_output=False,realtime_forwarding_tested=False,
    timing_limit='Timestamps measure Pico receive time. Samples within a packet retain order but have no separately measured generation time. This does not establish transport latency or actuator timing.')
a.prefix.with_suffix('.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
a.prefix.with_name(a.prefix.name+'-samples.json').write_text(json.dumps(timeline,indent=2),encoding='utf-8')
print(json.dumps(summary,indent=2))
