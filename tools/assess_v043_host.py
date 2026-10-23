"""Classify real-host 120s acceptance. Clean early shutdown is never a full pass."""
import argparse,json,pathlib,sys
ROOT=pathlib.Path(__file__).absolute().parents[1];sys.path.insert(0,str(ROOT/'handoff/2026-10-22/work'))
from bridge_process import input_end_check_succeeded
from bridge_input import NEUTRAL

def assess(program,capture,baseline,human_inputs=False):
    child=program.get('child',{});wire=child.get('events',[])
    motor=[e['motors_hex'] for e in capture.get('events',[]) if e['motors_hex'] is not None]
    relay=child.get('input_relay',{});start=child.get('live_started_at_pc_clock',0)
    delta=(capture.get('generation',0)-baseline.get('generation',0))&0xffffffff
    identity=program.get('firmware_preflight',{})
    checks=dict(strict_program=input_end_check_succeeded(child,program.get('child_exit')),
        strict_parent=program.get('status')=='PASSED_V043_SWITCH_INPUT_END_PROGRAM_CHECKS',
        firmware_verified=identity.get('verified') is True and identity.get('variant')=='v043' and identity.get('baseline_generation')==baseline.get('generation'),
        new_generation=delta==1,persistent_journal=capture.get('no_flash_marker')==0 and capture.get('target_offset') in ('0xe0000','0xf0000'),
        complete_journal=capture.get('crc_valid') is True and capture.get('complete') is True and capture.get('dropped_events')==0,
        terminal_confirmed=capture.get('stream_end')=='client_confirmed',
        exact_fields=motor==[e['motors'] for e in wire] and bool(motor),
        contiguous_wire=[e['sequence'] for e in wire]==list(range(len(wire))),
        configuration_unchanged=program.get('configuration_unchanged') is True,
        parent_stop=program.get('runtime_disable_ack') is True,guardian_clean=program.get('guardian_killed_child') is False,
        no_errors=not any(obj.get(k) for obj in (program,child) for k in ('error','cleanup_error','pico_reset_error')))
    integrity=all(checks.values())
    duration_checks=dict(firmware_live_deadline=capture.get('reason')=='capture_deadline' and capture.get('elapsed_ms',0)>=120000,
        full_observed_window=117<=child.get('live_elapsed_seconds',0)<=123,
        late_input_observed=isinstance(relay.get('last_read_at_pc_clock'),(int,float)) and relay['last_read_at_pc_clock']-start>=115,
        late_nonneutral_observed=isinstance(relay.get('last_nonneutral_at_pc_clock'),(int,float)) and relay['last_nonneutral_at_pc_clock']-start>=100,
        final_neutral=relay.get('last_pro_input')==NEUTRAL.hex(),human_inputs=human_inputs is True)
    status='INCOMPLETE'
    if integrity:
        status={'capacity_limit':'CLEAN_EARLY_CAPACITY_LIMIT','boot_limit':'CLEAN_EARLY_BOOT_LIMIT'}.get(capture.get('reason'),'INCOMPLETE_120S_ACCEPTANCE')
        if all(duration_checks.values()):status='PASSED_V043_SWITCH_120S_INPUT_ACCEPTANCE'
    return dict(status=status,integrity_checks=checks,duration_checks=duration_checks,journal_generation=capture.get('generation'),
        transport_120s_validated=integrity and all(duration_checks[k] for k in ('firmware_live_deadline','full_observed_window','late_input_observed','final_neutral')),
        pending_checks=[k for k,v in dict(checks,**duration_checks).items() if not v],
        end_reason=capture.get('reason'),observed_live_seconds=child.get('live_elapsed_seconds'),motor_fields=len(motor),
        scope='Input-only Switch 2 acceptance; no Flydigi waveform output or game haptics validation')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('program','capture','baseline','output'):p.add_argument('--'+name,type=pathlib.Path,required=True)
    p.add_argument('--human-inputs',action='store_true');a=p.parse_args()
    load=lambda path:json.loads(path.read_text(encoding='utf-8-sig'))
    baseline_doc=load(a.baseline);baseline=baseline_doc.get('newest',baseline_doc.get('capture'))
    if not isinstance(baseline,dict):raise ValueError('Baseline must contain a decoded newest or capture journal')
    result=assess(load(a.program),load(a.capture)['newest'],baseline,a.human_inputs)
    with a.output.open('x',encoding='utf-8') as h:json.dump(result,h,indent=2)
    print(json.dumps(result,indent=2));raise SystemExit(0 if result['status']=='PASSED_V043_SWITCH_120S_INPUT_ACCEPTANCE' else 1)
