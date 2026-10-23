"""Correlate one explicitly armed game test with journal, output and human evidence."""
import argparse,json,pathlib,sys
ROOT=pathlib.Path(__file__).absolute().parents[1];sys.path.insert(0,str(ROOT/'handoff/2026-10-22/work'))
from bridge_process import game_end_check_succeeded
from switch_hd_decode import Decoder
p=argparse.ArgumentParser(description=__doc__)
for name in ('program','capture','baseline','output'):p.add_argument('--'+name,type=pathlib.Path,required=True)
for name in ('human-game-pulse','human-prearm-silent','human-stopped'):p.add_argument('--'+name,action='store_true')
a=p.parse_args();program=json.loads(a.program.read_text(encoding='utf-8-sig'));child=program.get('child',{})
capture=json.loads(a.capture.read_text(encoding='utf-8-sig'))['newest'];baseline=json.loads(a.baseline.read_text(encoding='utf-8-sig'))['newest']
events=[e for e in capture['events'] if e['motors_hex'] is not None];wire=child.get('events',[])
anchor=child.get('source_clock_anchor',{});arm=child.get('armed_at_pc_clock')
arm_source=anchor.get('source_us',0)+(arm-anchor.get('pc_clock',0))*1e6 if isinstance(arm,(float,int)) and anchor else None
decoders=[Decoder(),Decoder()];first_after=[None,None];post_active=[0,0]
for event in events:
    raw=bytes.fromhex(event['motors_hex'])
    for side,word in enumerate((raw[:4],raw[4:])):
        for index,sample in enumerate(decoders[side].decode(word)['samples']):
            at=event['at_us']+index*5000
            if arm_source is not None and at>=arm_source and sample['state_complete'] and (sample['low_amplitude'] or sample['high_amplitude']):
                post_active[side]+=1
                if first_after[side] is None:first_after[side]=(at-arm_source)/1000
delta=(capture['generation']-baseline['generation'])&0xffffffff
checks=dict(strict_game_program=game_end_check_succeeded(child,program.get('child_exit')),
    strict_parent=program.get('status')=='PASSED_V042_SWITCH_GAME_PROGRAM_CHECKS',new_generation=0<delta<0x80000000,
    journal_complete=capture['crc_valid'] and capture['complete'],persistent_end=capture['stream_end']=='client_confirmed',
    all_fields_exact=[e['motors_hex'] for e in events]==[e['motors'] for e in wire],
    contiguous_wire=[e['sequence'] for e in wire]==list(range(len(wire))),
    staged_explicit_arm=child.get('staged_game') is True and arm_source is not None,
    silent_preparation=child.get('pre_arm_output_frames')==0 and child.get('pre_arm_prompt_counts')==[0,0],
    post_arm_source_both_sides=all(post_active),one_complete_prompt_each=child.get('prompt_counts')==[1,1] and child.get('active_samples')==[120,120],
    output_bound=child.get('maximum_offset',999)<=12,parent_disabled=program.get('runtime_disable_ack') is True,
    configuration_unchanged=program.get('configuration_unchanged') is True,guardian_not_killed=program.get('guardian_killed_child') is False,
    no_cleanup_errors=not any(obj.get(k) for obj in (program,child) for k in ('error','cleanup_error','pico_reset_error')),
    human_game_pulse=a.human_game_pulse,human_prearm_silent=a.human_prearm_silent,human_stopped=a.human_stopped)
result=dict(status='PASSED_STAGED_GAME_LIMITED_NOTIFICATION' if all(checks.values()) else 'INCOMPLETE',checks=checks,
    journal_generation=capture['generation'],motor_fields=len(events),received_fields=len(wire),first_active_ms_after_arm=first_after,decoded_post_arm_active_groups=post_active,
    scope='One offline door-entry trial; calibrated 120ms notification mapping, not original HD-rumble fidelity or long-term stability',
    human_evidence='User explicitly confirmed armed, waited 1s, entered door with extra short pulse; prearm silent and no residual',
    source_reports=[a.program.name,a.capture.name,a.baseline.name])
with a.output.open('x',encoding='utf-8') as h:json.dump(result,h,indent=2)
print(json.dumps(result,indent=2));raise SystemExit(0 if all(checks.values()) else 1)
