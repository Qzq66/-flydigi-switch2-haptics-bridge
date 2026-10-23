"""Assess muted input continuity separately from game-haptics success."""
import argparse,json,pathlib
p=argparse.ArgumentParser(description=__doc__)
for name in ('program','capture','baseline','output'):p.add_argument('--'+name,type=pathlib.Path,required=True)
a=p.parse_args();program=json.loads(a.program.read_text(encoding='utf-8-sig'));child=program.get('child',{})
capture=json.loads(a.capture.read_text(encoding='utf-8-sig'))['newest'];baseline=json.loads(a.baseline.read_text(encoding='utf-8-sig'))['newest']
wire=child.get('events',[]);local=[e['motors_hex'] for e in capture['events'] if e['motors_hex'] is not None]
reads_after=child.get('input_relay',{}).get('nonneutral_reads',0)-child.get('input_reads_at_mute',0)
checks=dict(new_generation=0<(capture['generation']-baseline['generation'])&0xffffffff<0x80000000,
    complete_crc=capture['complete'] and capture['crc_valid'],persistent_end_confirmed=capture['stream_end']=='client_confirmed',
    all_motor_fields_exact=local==[e['motors'] for e in wire],sequence_contiguous=[e['sequence'] for e in wire]==list(range(len(wire))),
    terminal_complete=child.get('ended_reason')=='terminal stream complete' and child.get('terminal_received') is True and child.get('terminal_ack_replied') is True,
    muted_at_expected_cap=child.get('output_fault')=='calibrated prompt count cap',
    no_waveforms_after_mute=type(child.get('output_frames_at_mute')) is int and child.get('output_frames')==child['output_frames_at_mute'],
    muted_loop_continued=child.get('muted_frames',0)>0,input_active_after_mute=reads_after>0,
    bounded_output=child.get('maximum_offset',999)<=12 and child.get('prompt_counts')==[3,3] and child.get('active_samples')==[360,360],
    collector_ended=child.get('collector_ended') is True,timer_released=child.get('timer_released') is True,
    parent_disabled=program.get('runtime_disable_ack') is True,configuration_unchanged=program.get('configuration_unchanged') is True,
    no_cleanup_errors=not any(obj.get(k) for obj in (program,child) for k in ('error','cleanup_error','pico_reset_error')),
    guardian_not_killed=program.get('guardian_killed_child') is False)
result=dict(status='PASSED_MUTED_INPUT_END_CHECKS' if all(checks.values()) else 'INCOMPLETE',checks=checks,log_generation=capture['generation'],motor_fields=len(local),received_fields=len(wire),nonneutral_reads_after_mute=reads_after,game_haptics_validated=False,human_controllability='record separately',source_reports=[a.program.name,a.capture.name,a.baseline.name])
with a.output.open('x',encoding='utf-8') as h:json.dump(result,h,indent=2)
print(json.dumps(result,indent=2));raise SystemExit(0 if all(checks.values()) else 1)
