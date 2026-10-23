"""Assess one 120s explicitly armed game trial; no hardware access."""
import argparse,json,pathlib,sys
from v043_game_gate import authorize,ROOT
sys.path.insert(0,str(ROOT/'handoff/2026-10-22/work'))
from bridge_process import game_end_check_succeeded
from switch_hd_decode import Decoder
from bridge_input import NEUTRAL

def assess(program,capture,baseline,proof,human_pulse=False,human_silent=False,human_stopped=False):
    child=program.get('child',{});wire=child.get('events',[]);events=[e for e in capture.get('events',[]) if e['motors_hex'] is not None]
    anchor=child.get('source_clock_anchor',{});arm=child.get('armed_at_pc_clock');start=child.get('live_started_at_pc_clock',0)
    arm_source=anchor['source_us']+(arm-anchor['pc_clock'])*1e6 if isinstance(arm,(int,float)) and anchor else None
    decoders=[Decoder(),Decoder()];post=[0,0];first=[None,None]
    # The network clock starts at bridge_init; the persistent journal starts
    # at capture_init. Field equality binds them, but their epochs differ.
    # Compare arming only with network timestamps from the same source clock.
    for event in wire:
        raw=bytes.fromhex(event['motors'])
        for side,word in enumerate((raw[:4],raw[4:])):
            for i,sample in enumerate(decoders[side].decode(word)['samples']):
                at=event['at_us']+i*5000
                if arm_source is not None and at>=arm_source and sample['state_complete'] and (sample['low_amplitude'] or sample['high_amplitude']):
                    post[side]+=1
                    if first[side] is None:first[side]=(at-arm_source)/1000
    gate=program.get('input_acceptance_gate',{});identity=program.get('firmware_preflight',{});relay=child.get('input_relay',{})
    checks=dict(strict_game_program=game_end_check_succeeded(child,program.get('child_exit')),
        strict_parent=program.get('status')=='PASSED_V043_SWITCH_GAME_PROGRAM_CHECKS',
        input_acceptance_bound=proof.get('verified') is True and gate==proof and identity.get('firmware_sha256')==proof.get('firmware_sha256'),
        exact_new_generation=((capture.get('generation',0)-baseline.get('generation',0))&0xffffffff)==1 and identity.get('baseline_generation')==baseline.get('generation'),
        journal_complete=capture.get('crc_valid') is True and capture.get('complete') is True and capture.get('no_flash_marker')==0 and capture.get('dropped_events')==0 and capture.get('target_offset') in ('0xe0000','0xf0000'),
        persistent_end=capture.get('stream_end')=='client_confirmed',
        all_fields_exact=bool(events) and [e['motors_hex'] for e in events]==[e['motors'] for e in wire],
        contiguous_wire=[e['sequence'] for e in wire]==list(range(len(wire))),
        full_live_window=capture.get('reason')=='capture_deadline' and capture.get('elapsed_ms',0)>=120000 and 117<=child.get('live_elapsed_seconds',0)<=123,
        staged_explicit_arm=child.get('staged_game') is True and arm_source is not None,
        arm_within_window=isinstance(arm,(int,float)) and 0<=arm-start<=115,
        silent_preparation=child.get('pre_arm_output_frames')==0 and child.get('pre_arm_prompt_counts')==[0,0],
        post_arm_source_both_sides=all(post),one_complete_prompt_each=child.get('prompt_counts')==[1,1] and child.get('active_samples')==[120,120],
        output_bound=child.get('maximum_offset',999)<=12,
        relay_observed=relay.get('nonneutral_reads',0)>0,
        final_neutral=relay.get('last_pro_input')==NEUTRAL.hex(),
        input_through_end=isinstance(relay.get('last_read_at_pc_clock'),(int,float)) and relay['last_read_at_pc_clock']-start>=115,
        parent_disabled=program.get('runtime_disable_ack') is True,configuration_unchanged=program.get('configuration_unchanged') is True,
        guardian_not_killed=program.get('guardian_killed_child') is False,
        no_cleanup_errors=not any(obj.get(k) for obj in (program,child) for k in ('error','cleanup_error','pico_reset_error','output_fault')),
        human_game_pulse=human_pulse is True,human_prearm_silent=human_silent is True,human_stopped=human_stopped is True)
    return dict(status='PASSED_V043_120S_STAGED_GAME_LIMITED_NOTIFICATION' if all(checks.values()) else 'INCOMPLETE',checks=checks,
        journal_generation=capture.get('generation'),motor_fields=len(events),first_active_ms_after_arm=first,decoded_post_arm_active_groups=post,
        observed_live_seconds=child.get('live_elapsed_seconds'),scope='One offline door-entry trial, calibrated 120ms notifications; not original HD fidelity or long-term stability')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('program','capture','baseline','input-acceptance-bundle','output'):p.add_argument('--'+name,type=pathlib.Path,required=True)
    for name in ('human-game-pulse','human-prearm-silent','human-stopped'):p.add_argument('--'+name,action='store_true')
    a=p.parse_args();load=lambda path:json.loads(path.read_text(encoding='utf-8-sig'));program=load(a.program)
    proof=authorize(a.input_acceptance_bundle,program['firmware_preflight'])
    result=assess(program,load(a.capture)['newest'],load(a.baseline)['newest'],proof,a.human_game_pulse,a.human_prearm_silent,a.human_stopped)
    with a.output.open('x',encoding='utf-8') as h:json.dump(result,h,indent=2)
    print(json.dumps(result,indent=2));raise SystemExit(0 if all(result['checks'].values()) else 1)
