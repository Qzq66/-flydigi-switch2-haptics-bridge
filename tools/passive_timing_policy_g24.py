"""Generation24 passive timing candidate; frozen G22/G23 sources stay unchanged."""
import json
from passive_transport_policy import ROOT,digest,build_plan as previous_plan,PassiveSession,collection_completed

def build_plan():
    plan=previous_plan();docs=ROOT/'docs'
    baseline_path=docs/'V043_READY_BASELINE_20261025-162911.json'
    proof_path=docs/'FIDELITY_G23_RECOVERY_ASSESSMENT_20261025-162237.json'
    baseline=json.loads(baseline_path.read_text());proof=json.loads(proof_path.read_text())
    if (baseline.get('status')!='V043_FLASH_READY_VERIFIED' or baseline.get('baseline_generation')!=24
        or baseline.get('previous_generation')!=23 or baseline.get('physical_full_readback_verified') is not True
        or baseline.get('outside_journal_unchanged') is not True or baseline.get('flash_write') is not False
        or baseline.get('firmware_sha256')!=plan['firmware_sha256']):raise ValueError('Verified generation24 baseline required')
    if (proof.get('status')!='PASSED_POST_EPISODE_FAULT_LATCH_AND_CAPTURE_CONTINUATION'
        or proof.get('generation')!=24 or len(proof.get('checks',{}))!=24 or not all(proof['checks'].values())):raise ValueError('Bound G23 recovery proof required')
    for name,h in proof['source_sha256'].items():
        if digest(ROOT/name)!=h:raise ValueError('Recovery evidence changed: '+name)
    capture=json.loads((docs/'V043_HOST_CAPTURE_20261025-162834.json').read_text())
    if capture['full_flash_sha256']!=baseline['full_flash_sha256']:raise ValueError('Generation24 full-Flash proof differs')
    plan.update(version=2,kind='no_actuator_poll_stage_timing_diagnostic',expected_flash_generation=24,
        expected_full_flash_sha256=baseline['full_flash_sha256'],baseline_proof_sha256=digest(baseline_path),
        recovery_proof_sha256=digest(proof_path),input_forwarding='read_xinput_then_send_fixed_neutral')
    for name in ('passive_timing_policy_g24.py','run_passive_timing_g24.py','poll_timing_probe.py'):
        plan['source_sha256'][name]=digest(ROOT/'tools'/name)
    return plan

def validate_plan(plan):
    if plan!=build_plan():raise ValueError('G24 timing plan or bound source changed')
