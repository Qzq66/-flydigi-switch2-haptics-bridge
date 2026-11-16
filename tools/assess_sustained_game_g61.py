"""Pure same-trial Flash/wire and explicit human acceptance; no hardware access."""
import argparse,json,pathlib
from sustained_game_policy_g61 import game_parent_passed,validate_game_plan,digest
from switch_hd_decode import Decoder
from sustained_validation import assess_sustained as assess_written
from phase_gap_validation import assess_phase_gap
from haptic_fidelity_candidate import reconstruct,ZERO,KEYS

def source_reference(child):
    """Re-decode only the generated source interval, including all prefix state.

    Later game rumble is archived but intentionally muted by the one-shot latch;
    it must not be mistaken for another emitted episode or reconstructed tail.
    """
    anchor=child['source_clock_anchor'];start=anchor['source_us']+(child['armed_at_pc_clock']-anchor['pc_clock'])*1e6
    end=start+child['output_frames']*8000;decoders=[Decoder(),Decoder()];timelines=[[],[]]
    for event in child['events']:
        if event['at_us']>=end:break
        raw=bytes.fromhex(event['motors'])
        for side in (0,1):
            decoded=decoders[side].decode(raw[side*4:side*4+4])
            for index,sample in enumerate(decoded['samples']):
                at=event['at_us']+5000*index
                if not start<=at<end:continue
                if not sample['state_complete']:raise ValueError('Unknown source state during emitted interval')
                values={key:sample[key] for key in KEYS} if event['flags']&4 else dict(ZERO)
                timelines[side].append(dict(at_us=at,**values))
    for timeline in timelines:
        if not timeline or timeline[-1]['low_amplitude'] or timeline[-1]['high_amplitude']:raise ValueError('Emitted source interval lacks real neutral ending')
    result=reconstruct(timelines,start,end)
    return dict(active_ms=[sum(side) for side in result['active']],peak_code=max(abs(v-128) for side in result['pcm'] for v in side),
        squared_code_sum=[sum((v-128)**2 for v in side) for side in result['pcm']],final_samples_neutral=all(side[-1]==128 for side in result['pcm']))

def assess(program,plan,capture_report,baseline_report,plan_sha256,human_event=False,human_silent=False,human_stopped=False,human_input=False):
    c=program.get('child',{});cap=capture_report.get('newest',{});base=baseline_report.get('newest',{})
    wire=c.get('events',[]);local=[e['motors_hex'] for e in cap.get('events',[]) if e.get('motors_hex') is not None]
    reference=None;reference_error=None
    try:reference=source_reference(c)
    except (KeyError,ValueError,TypeError,OverflowError) as exc:reference_error=repr(exc)
    checks=dict(strict_parent=game_parent_passed(program,plan),parent_program_status=program.get('status')=='PASSED_SWITCH_FIDELITY_PROGRAM_PENDING_FLASH_LOG',
        plan_bound=program.get('plan_sha256')==plan_sha256,readback_verified=capture_report.get('status')=='V043_HOST_FLASH_READBACK_VERIFIED' and bool(capture_report.get('checks')) and all(capture_report['checks'].values()),
        baseline_generation=base.get('generation')==plan['expected_flash_generation'],baseline_full_flash=baseline_report.get('full_flash_sha256')==plan['expected_full_flash_sha256'],
        exactly_one_new_generation=((cap.get('generation',0)-base.get('generation',0))&0xffffffff)==1,
        program_unchanged=capture_report.get('firmware_sha256')==plan['firmware_sha256'],
        full_source_motor_fields=bool(local) and local==[e['motors'] for e in wire],
        complete_persistent_journal=cap.get('crc_valid') is True and cap.get('complete') is True and cap.get('no_flash_marker')==0 and cap.get('dropped_events')==0 and cap.get('target_offset') in ('0xe0000','0xf0000'),
        confirmed_log_end=cap.get('stream_end')=='client_confirmed' and cap.get('reason')=='capture_deadline',
        independent_source_reconstruction=reference is not None and reference['final_samples_neutral'] and all(reference[key]==c.get(key) for key in ('active_ms','peak_code','squared_code_sum')),
        human_game_event=human_event is True,human_prearm_silent=human_silent is True,human_stopped=human_stopped is True,human_postmute_input=human_input is True)
    gap=assess_phase_gap(c)
    checks['phase_gap_integrity']=gap['passed']
    pcm=assess_written(c)
    checks['written_pcm_matches_independent_source']=pcm['passed']
    return dict(phase_gap=gap,written_pcm=pcm,status='PASSED_BOUNDED_60_SECOND_SIX_EVENT_GAME' if all(checks.values()) else 'INCOMPLETE',checks=checks,
        journal_generation=cap.get('generation'),motor_fields=len(local),active_ms=c.get('active_ms'),peak_code=c.get('peak_code'),squared_code_sum=c.get('squared_code_sum'),source_reference=reference,source_reference_error=reference_error,
        scope='Three bounded live game actions with startup qualification; not measured original HD/HD2 physical equivalence or long-duration stability.')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('program','plan','capture','baseline','output'):p.add_argument('--'+n,type=pathlib.Path,required=True)
    for n in ('human-event','human-silent','human-stopped','human-input'):p.add_argument('--'+n,action='store_true')
    a=p.parse_args();load=lambda path:json.loads(path.read_text(encoding='utf-8-sig'));plan=load(a.plan);validate_game_plan(plan)
    result=assess(load(a.program),plan,load(a.capture),load(a.baseline),digest(a.plan),a.human_event,a.human_silent,a.human_stopped,a.human_input)
    result['source_sha256']={n:digest(getattr(a,n)) for n in ('program','plan','capture','baseline')}
    with a.output.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps(result,indent=2));return 0 if all(result['checks'].values()) else 1

if __name__=='__main__':raise SystemExit(main())
