"""Offline technical acceptance plus explicit subjective frequency feedback."""
import argparse,json,pathlib
from frequency_ab_plan import validate_plan,ab_child_succeeded,digest

def assess(program,plan,plan_hash,bilateral,stopped,sensation):
    validate_plan(plan);c=program.get('child',{})
    a,b=plan['segments'];segments=c.get('segments',[])
    checks=dict(plan_hash=program.get('plan_sha256')==plan_hash,
        strict_child=ab_child_succeeded(c,program.get('child_exit'),plan,program.get('guardian_killed_child',True)),
        strict_parent=program.get('status')=='PASSED_FIDELITY_AB_PROGRAM_AND_CONFIG',
        final_stop_ack=program.get('runtime_disable_ack') is True,
        identity=program.get('identity_matches') is True,state=program.get('state_matches') is True,
        four_config_areas=program.get('ram_matches')=={'global':True,'mapping':True,'lighting':True,'motors':True},
        factory_config_unchanged=program.get('configuration_unchanged') is True,
        no_persistent_commands=program.get('persistent_flydigi_commands')==0 and c.get('persistent_flydigi_commands')==0,
        no_pico_or_switch_access=program.get('pico_access') is False and program.get('switch_access') is False,
        no_errors=not any(o.get(k) for o in (program,c) for k in ('error','cleanup_error')),
        matched_duration_and_peak=a['samples_per_side']==b['samples_per_side']==208 and a['peak_code']==b['peak_code']==8,
        matched_digital_dose=a['squared_code_sum']==b['squared_code_sum']==[6496,6496],
        human_bilateral=bilateral is True,human_stopped=stopped is True)
    return dict(status='PASSED_CONTROLLED_FREQUENCY_COMPARISON_WITH_FEEDBACK' if all(checks.values()) else 'INCOMPLETE',
        checks=checks,sensation=sensation,frequency_texture_reported=sensation in ('texture_similar_strength','texture_and_strength'),
        subjective_strength_similar=sensation=='texture_similar_strength',
        frequencies_hz=[80,240],active_duration_ms=200,neutral_tail_ms=8,peak_code=8,
        digital_squared_code_sum_per_clip_per_side=6496,
        confirmed_gap_seconds=(segments[1]['started_at_monotonic']-segments[0]['stop']['confirmed_at_monotonic']) if checks['strict_child'] else None,
        physical_force_measured=False,frequency_response_calibrated=False,native_fidelity_validated=False,
        scope='One fixed-order unblinded synthetic pair; subjective frequency discrimination, not objective equal force or native equivalence.')

def main():
    p=argparse.ArgumentParser()
    for n in ('program','plan','output'):p.add_argument('--'+n,type=pathlib.Path,required=True)
    p.add_argument('--bilateral',action='store_true');p.add_argument('--stopped',action='store_true')
    p.add_argument('--sensation',choices=['texture_similar_strength','strength_only','texture_and_strength','unclear'],required=True)
    a=p.parse_args();load=lambda f:json.loads(f.read_text(encoding='utf-8-sig'))
    result=assess(load(a.program),load(a.plan),digest(a.plan),a.bilateral,a.stopped,a.sensation)
    result['evidence_sha256']=dict(program=digest(a.program),plan=digest(a.plan),assessor=digest(pathlib.Path(__file__)))
    with a.output.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps(result,indent=2));return 0 if all(result['checks'].values()) else 1
if __name__=='__main__':raise SystemExit(main())
