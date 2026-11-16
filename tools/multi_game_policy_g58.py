"""Independent12ms limited game candidate bound to verified57."""
import json
from fidelity_game_policy_gap42 import ROOT,digest,build_game_plan as previous_plan,GameSession,can_click,game_child_passed as previous_child,game_parent_passed as previous_parent

def build_game_plan():
    plan=previous_plan();ready=ROOT/'docs'/'V043_READY_BASELINE_20261029-235533.json';b=json.loads(ready.read_text())
    if b['baseline_generation']!=58 or b['previous_generation']!=57 or not b['physical_full_readback_verified'] or not b['outside_journal_unchanged'] or b['flash_write'] or b['firmware_sha256']!=plan['firmware_sha256']:raise ValueError('Verified58 required')
    for r in json.loads((ROOT/'docs/FIDELITY_GAP42_RUN_FREEZE_20261027-234740.json').read_text())['files']:
        if digest(ROOT/r['path'])!=r['sha256']:raise ValueError('Accepted runtime freeze mismatch')
    plan.update(version=13,expected_flash_generation=58,expected_full_flash_sha256=b['full_flash_sha256'],baseline_proof_sha256=digest(ready),scope='Recovered accepted GAP42 PC runtime, current57 binding and12ms receive budget only; not hardware accepted.')
    for n in ('multi_game_policy_g58.py','run_multi_game_g58.py','assess_multi_game_g58.py'):
        plan['tool_sha256'][n]=digest(ROOT/'tools'/n)
    plan['phase_observation']['underlying_receive_timeout_seconds']=.012
    plan['receive_budget_seconds']=.012
    plan['default_game_replaced']=False
    plan['tool_sha256']['receive_budget12_transport.py']=digest(ROOT/'tools/receive_budget12_transport.py')
    proof=ROOT/'docs/UPDATED_CONFIG_AMP9_ASSESSMENT_2026-10-29.json'
    evidence=json.loads(proof.read_text())
    if not all(evidence['checks'].values()):raise ValueError('Updated config exit proof incomplete')
    plan['updated_config_exit_sha256']=digest(proof)
    plan['limits']['maximum_offset']=9
    plan['tool_sha256']['updated_config_game_owner.py']=digest(ROOT/'tools/updated_config_game_owner.py')
    plan['scope']='Independent bounded three-event game candidate; not yet hardware validated.'
    plan['multi_event']=dict(maximum_events=3,quiet_ms=500,session_activity_ms_per_side=960,session_squared_codes_per_side=24000,armed_seconds=15)
    for name in ('bounded_multi_event_renderer.py','bounded_multi_event_session.py','multi_event_game_session.py','multi_event_validation.py','multi_event_game_window.py'):
        plan['tool_sha256'][name]=digest(ROOT/'tools'/name)
    return plan

def validate_game_plan(plan):
    if plan!=build_game_plan():raise ValueError('Receive12G57 plan or source mismatch')

import math
from bridge_input import NEUTRAL
from multi_event_game_session import MultiGameSession as GameSession
from multi_event_validation import assess_multi
from phase_gap_validation import assess_phase_gap

def game_child_passed(c):
    try:
        if not all(c.get(k) is True for k in ('manual_armed','output_stop_confirmed','terminal_received','terminal_ack_replied','collector_ended','timer_released','terminal_observed')):return False
        if any(c.get(k) for k in ('error','output_fault','cleanup_error','finalization_errors')):return False
        if c['pre_arm_output_frames']!=0 or c['muted_reason']!='three-event session completed':return False
        if c.get('host_flash_write') is not False or c.get('persistent_flydigi_commands')!=0 or c.get('actual_switch_game') is not True:return False
        for values,limit in ((c['active_ms'],960),(c['squared_code_sum'],24000)):
            if len(values)!=2 or not all(type(v) in (int,float) and math.isfinite(v) and 0<v<=limit for v in values):return False
        if not assess_multi(c)['passed'] or not assess_phase_gap(c)['passed']:return False
        late=c['output_lateness_seconds'];writes=c['output_write_seconds'];events=c['events'];relay=c['input_relay']
        diagnostics=c['transport_diagnostics']
        if (diagnostics['responses']<=0 or diagnostics['poll_calls']<diagnostics['responses']
            or not diagnostics['recent'] or len(diagnostics['observed_boot_ids'])!=1):return False
        return (0<c['peak_code']<=9 and 0<c['output_frames']<=1900 and len(late)==len(writes)==c['output_frames']
            and all(math.isfinite(v) and 0<=v<=.004 for v in late) and all(math.isfinite(v) and 0<=v<=.080 for v in writes)
            and 0<len(events)<=2725 and [e['sequence'] for e in events]==list(range(len(events)))
            and relay['last_pro_input']==NEUTRAL.hex() and relay['reads_after_output_stop']>=5
            and relay['nonneutral_reads_after_output_stop']>0 and relay['last_nonneutral_at_pc_clock']>c['stopped_at_pc_clock']+.5
            and relay['last_read_at_pc_clock']>=c['stopped_at_pc_clock']+5
            and 110<=c['live_elapsed_seconds']<=123 and c['status']=='PASSED_SWITCH_FIDELITY_CHILD_PENDING_FLASH_LOG')
    except (KeyError,TypeError,ValueError,OverflowError):return False

def game_parent_passed(p,plan):
    try:
        from game_input_liveness import passed as liveness_passed
        f=p['firmware_preflight'];proof=p['accepted_input_proof']
        if not liveness_passed(p.get('pc_input_liveness',{})) or p['child']['input_relay']['slot']!=p['pc_input_liveness']['slot']:return False
        return (game_child_passed(p['child']) and p['child_exit']==0 and p['guardian_killed_child'] is False
            and all(p.get(k) is True for k in ('runtime_disable_ack','configuration_unchanged','post_neutral_discovery_ready'))
            and p.get('identity_matches') is True and p.get('state_matches') is True and len(p.get('ram_matches',{}))==4 and all(p['ram_matches'].values())
            and not any(p.get(k) for k in ('error','cleanup_error')) and f['verified'] is True
            and f['firmware_sha256']==plan['firmware_sha256'] and f['baseline_generation']==plan['expected_flash_generation']
            and f['installed_snapshot_sha256']==plan['expected_full_flash_sha256']
            and proof['verified'] is True and proof['firmware_sha256']==f['firmware_sha256'] and proof['accepted_input_generation']==plan['accepted_input_generation']
            and proof.get('source_hashes')==plan['accepted_input_source_hashes']
            and p['host_flash_write'] is False and p['persistent_flydigi_commands']==0
            and p.get('flash_log_validation_pending') is True and p.get('firmware_log_write_expected') is True)
    except (KeyError,TypeError):return False
