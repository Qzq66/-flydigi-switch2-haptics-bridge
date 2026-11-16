"""Bind actual28 installation separately from salvaged27 trial acceptance."""
import json
from passive_timing_policy_g26 import ROOT,digest,build_plan as previous_plan,PassiveSession,collection_completed

def build_plan():
    plan=previous_plan();docs=ROOT/'docs'
    ready=docs/'V043_READY_BASELINE_20261025-193016.json'
    proof_path=docs/'PASSIVE_POLL_TIMING_ASSESSMENT_20261025-165651.json'
    later_path=docs/'PICO_LATER_BOOT_G28_20261025-192724.json'
    baseline=json.loads(ready.read_text());proof=json.loads(proof_path.read_text());later=json.loads(later_path.read_text())
    if (baseline.get('status')!='V043_FLASH_READY_VERIFIED' or baseline.get('baseline_generation')!=28
        or baseline.get('physical_full_readback_verified') is not True or baseline.get('outside_journal_unchanged') is not True
        or baseline.get('flash_write') is not False or baseline.get('firmware_sha256')!=plan['firmware_sha256']):raise ValueError('Physical generation28 installation proof required')
    if (proof.get('status')!='MATCHED_TRIAL_JOURNAL_WITH_LATER_BOOT_NOT_STRICT_SINGLE_GENERATION_ACCEPTANCE'
        or proof.get('current_flash_generation')!=28 or proof.get('matched_trial_generation')!=27
        or proof.get('strict_single_generation_readback_passed') is not False
        or len(proof.get('checks',{}))!=21 or not all(proof['checks'].values())):raise ValueError('Preserve matched27 and separate28 provenance')
    for name,h in proof['source_sha256'].items():
        if digest(ROOT/name)!=h:raise ValueError('Reference evidence changed: '+name)
    n=later['record']
    if (later['full_flash_sha256']!=baseline['full_flash_sha256'] or n['generation']!=28
        or not n['crc_valid'] or not n['complete'] or n['no_flash_marker']!=0):raise ValueError('Current28 journal differs')
    plan.update(version=5,kind='no_actuator_same_thread_wake_and_receive_observation',expected_flash_generation=28,
        expected_full_flash_sha256=baseline['full_flash_sha256'],baseline_proof_sha256=digest(ready),
        recovery_proof_sha256=digest(proof_path),later_boot_proof_sha256=digest(later_path),
        prior_strict_single_generation_passed=False,collector_sleep_request_seconds=.004,
        timing_policy_change=False,collector_sleep_measurement=True)
    for name in ('passive_wake_policy_g28.py','run_passive_wake_g28.py','wake_timing_probe.py'):
        plan['source_sha256'][name]=digest(ROOT/'tools'/name)
    return plan

def validate_plan(plan):
    if plan!=build_plan():raise ValueError('G28 wake measurement plan or sources changed')
