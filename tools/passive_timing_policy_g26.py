"""Generation26 passive timing candidate; frozen G22/G23 sources stay unchanged."""
import json
from passive_timing_policy_g25 import ROOT,digest,build_plan as previous_plan,PassiveSession,collection_completed

def build_plan():
    plan=previous_plan();docs=ROOT/'docs'
    baseline_path=docs/'V043_READY_BASELINE_20261025-165544.json'
    proof_path=docs/'PASSIVE_POLL_TIMING_ASSESSMENT_20261025-164910.json'
    baseline=json.loads(baseline_path.read_text());proof=json.loads(proof_path.read_text())
    if (baseline.get('status')!='V043_FLASH_READY_VERIFIED' or baseline.get('baseline_generation')!=26
        or baseline.get('previous_generation')!=25 or baseline.get('physical_full_readback_verified') is not True
        or baseline.get('outside_journal_unchanged') is not True or baseline.get('flash_write') is not False
        or baseline.get('firmware_sha256')!=plan['firmware_sha256']):raise ValueError('Verified generation26 baseline required')
    if (proof.get('status')!='PASSED_RETAINED_POLL_TIMING_AND_SAME_TRIAL_JOURNAL'
        or proof.get('generation')!=26 or len(proof.get('checks',{}))!=22 or not all(proof['checks'].values())):raise ValueError('Bound stage-timing generation26 proof required')
    for name,h in proof['source_sha256'].items():
        if digest(ROOT/name)!=h:raise ValueError('Recovery evidence changed: '+name)
    capture=json.loads((docs/'V043_HOST_CAPTURE_20261025-165451.json').read_text())
    if capture['full_flash_sha256']!=baseline['full_flash_sha256']:raise ValueError('Generation26 full-Flash proof differs')
    plan.update(version=4,critical_context_required=True,kind='no_actuator_poll_stage_timing_diagnostic',expected_flash_generation=26,
        expected_full_flash_sha256=baseline['full_flash_sha256'],baseline_proof_sha256=digest(baseline_path),
        recovery_proof_sha256=digest(proof_path),input_forwarding='read_xinput_then_send_fixed_neutral')
    for name in ('passive_timing_policy_g26.py','run_passive_timing_g26.py','poll_timing_probe_v2.py'):
        plan['source_sha256'][name]=digest(ROOT/'tools'/name)
    return plan

def validate_plan(plan):
    if plan!=build_plan():raise ValueError('G26 timing plan or bound source changed')
