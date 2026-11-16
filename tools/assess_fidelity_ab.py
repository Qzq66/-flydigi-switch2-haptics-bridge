"""Combine one source-bound PC A/B report and explicit human feedback; no hardware."""
import argparse,hashlib,json,pathlib
from fidelity_ab_plan import validate_plan,ab_child_succeeded

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('program','plan','output'):p.add_argument('--'+name,type=pathlib.Path,required=True)
    for name in ('human-bilateral','human-texture-difference','human-stopped'):p.add_argument('--'+name,action='store_true')
    a=p.parse_args();plan=json.loads(a.plan.read_text(encoding='utf-8'));r=json.loads(a.program.read_text(encoding='utf-8'));validate_plan(plan)
    c=r.get('child',{});segments=c.get('segments',[])
    checks=dict(source_bound_plan=True,plan_hash_matches=r.get('plan_sha256')==hashlib.sha256(a.plan.read_bytes()).hexdigest(),
        strict_child=ab_child_succeeded(c,r.get('child_exit'),plan,r.get('guardian_killed_child',True)),
        strict_parent=r.get('status')=='PASSED_FIDELITY_AB_PROGRAM_AND_CONFIG',final_stop_ack=r.get('runtime_disable_ack') is True,
        identity_matches=r.get('identity_matches') is True,state_matches=r.get('state_matches') is True,
        four_config_areas_match=r.get('ram_matches')=={'global':True,'mapping':True,'lighting':True,'motors':True},configuration_unchanged=r.get('configuration_unchanged') is True,
        no_persistent_commands=r.get('persistent_flydigi_commands')==0 and c.get('persistent_flydigi_commands')==0,
        no_pico_or_switch_access=r.get('pico_access') is False and r.get('switch_access') is False,
        no_errors=not any(obj.get(key) for obj in (r,c) for key in ('error','cleanup_error')),
        human_bilateral=a.human_bilateral,human_b_texture_difference=a.human_texture_difference,human_stopped_without_residual=a.human_stopped)
    result=dict(status='PASSED_BOUNDED_FIDELITY_AB_WITH_HUMAN_FEEDBACK' if all(checks.values()) else 'INCOMPLETE',checks=checks,
        program=a.program.name,program_sha256=hashlib.sha256(a.program.read_bytes()).hexdigest(),plan=a.plan.name,plan_sha256=hashlib.sha256(a.plan.read_bytes()).hexdigest(),
        confirmed_gap_seconds=(segments[1]['started_at_monotonic']-segments[0]['stop']['confirmed_at_monotonic']) if checks['strict_child'] else None,
        frames=[s.get('playback',{}).get('frames') for s in segments],samples_per_side=[s.get('playback',{}).get('samples_per_side') for s in segments],
        playback_elapsed_seconds=[s.get('playback',{}).get('elapsed_seconds') for s in segments],
        human_feedback=dict(bilateral='A and B felt in both grips' if a.human_bilateral else 'not confirmed',difference='B had distinguishable texture or amplitude variation' if a.human_texture_difference else 'not confirmed',stop='Both stopped without residual' if a.human_stopped else 'not confirmed'),
        physical_original_fidelity_validated=False,live_switch_fidelity_validated=False,
        scope='One PC-only source-capture A/B comparison; different durations, frequencies and amplitudes. Confirms perceivable candidate and cleanup, not native-equivalent force, phase, frequency response or live timing.')
    with a.output.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps(result,indent=2));return 0 if all(checks.values()) else 1

if __name__=='__main__':raise SystemExit(main())
