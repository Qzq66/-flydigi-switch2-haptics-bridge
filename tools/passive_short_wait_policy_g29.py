"""Generation29 no-actuator comparison of12ms vs prior60ms receive budget."""
import json
from passive_wake_policy_g28 import ROOT,digest,build_plan as previous_plan,PassiveSession,collection_completed
from short_wait_transport import ShortWaitClient

def build_plan():
    plan=previous_plan();docs=ROOT/'docs'
    ready=docs/'V043_READY_BASELINE_20261025-200800.json'
    proof_path=docs/'PASSIVE_WAKE_ASSESSMENT_20261025-195942.json'
    baseline=json.loads(ready.read_text());proof=json.loads(proof_path.read_text())
    if (baseline.get('status')!='V043_FLASH_READY_VERIFIED' or baseline.get('baseline_generation')!=29
        or baseline.get('previous_generation')!=28 or baseline.get('physical_full_readback_verified') is not True
        or baseline.get('outside_journal_unchanged') is not True or baseline.get('flash_write') is not False
        or baseline.get('firmware_sha256')!=plan['firmware_sha256']):raise ValueError('Verified generation29 installation required')
    if (proof.get('status')!='PASSED_PASSIVE_WAKE_MEASUREMENT_AND_SAME_TRIAL_JOURNAL' or proof.get('generation')!=29
        or len(proof.get('checks',{}))!=24 or not all(proof['checks'].values())):raise ValueError('Complete previous wake-measurement evidence required')
    for name,h in proof['source_sha256'].items():
        if digest(ROOT/name)!=h:raise ValueError('Previous measurement changed: '+name)
    capture=json.loads((docs/'V043_HOST_CAPTURE_20261025-200642.json').read_text())
    if capture['full_flash_sha256']!=baseline['full_flash_sha256']:raise ValueError('Baseline/capture differs')
    if ShortWaitClient.RECEIVE_BUDGET_SECONDS!=.012:raise ValueError('Only explicit12ms comparison allowed')
    plan.update(version=6,kind='no_actuator_short_receive_wait_comparison',expected_flash_generation=29,
        expected_full_flash_sha256=baseline['full_flash_sha256'],baseline_proof_sha256=digest(ready),
        recovery_proof_sha256=digest(proof_path),reference_measurement_generation=29,
        earlier_late_return_strict_passed=False,prior_strict_single_generation_passed=True,
        receive_budget_seconds=.012,reference_receive_budget_seconds=.060,maximum_terminal_ack_attempts=3,
        wire_protocol_changed=False,receive_deadline_is_hard_realtime_guarantee=False)
    for name in ('passive_short_wait_policy_g29.py','run_passive_short_wait_g29.py','short_wait_transport.py'):
        plan['source_sha256'][name]=digest(ROOT/'tools'/name)
    return plan

def validate_plan(plan):
    if plan!=build_plan():raise ValueError('G29 short-receive comparison changed')
