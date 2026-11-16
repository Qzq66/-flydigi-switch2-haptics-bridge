"""Rebind the diagnostic-only two-component plan to existing verified generation35."""
import json
from passive_packet_policy_g32 import ROOT,digest,build_plan as previous_plan,PassiveSession,collection_completed

def build_plan():
    plan=previous_plan();ready=ROOT/'docs/V043_READY_BASELINE_20261026-202001.json';proof=ROOT/'docs/PASSIVE_REBASE_G35_20261026.json'
    baseline=json.loads(ready.read_text());prior=json.loads(proof.read_text())
    if (baseline.get('baseline_generation')!=35 or baseline.get('previous_generation')!=32
        or baseline.get('physical_full_readback_verified') is not True or baseline.get('flash_write') is not False
        or baseline.get('firmware_sha256')!=plan['firmware_sha256']):raise ValueError('Physical generation35 required')
    if (prior.get('status')!='VERIFIED_PREEXISTING_JOURNAL_G35_NOT_A_NEW_TEST' or not all(prior['checks'].values())
        or prior['full_flash_sha256']!=baseline['full_flash_sha256']):raise ValueError('Existing journal rebase evidence required')
    plan.update(version=10,kind='no_actuator_two_components_rebound_to_preexisting_g35',expected_flash_generation=35,
        expected_full_flash_sha256=baseline['full_flash_sha256'],baseline_proof_sha256=digest(ready),rebase_proof_sha256=digest(proof))
    for name in ('passive_packet_policy_g35.py','run_passive_packet_g35.py','run_pktmon_passive_g35.ps1'):
        plan['source_sha256'][name]=digest(ROOT/'tools'/name)
    return plan

def validate_plan(plan):
    if plan!=build_plan():raise ValueError('G35 plan or sources changed')
