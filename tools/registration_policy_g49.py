"""No-actuator registration input diagnostic bound to verified generation49."""
import json
from passive_transport_policy import ROOT,digest,build_plan as previous_plan,PassiveSession,collection_completed

def build_plan():
    plan=previous_plan();ready=ROOT/'docs'/'V043_READY_BASELINE_20261028-211015.json';b=json.loads(ready.read_text())
    if b['baseline_generation']!=49 or b['previous_generation']!=47 or not b['physical_full_readback_verified'] or not b['outside_journal_unchanged'] or b['flash_write'] or b['firmware_sha256']!=plan['firmware_sha256']:raise ValueError('Verified49 required')
    plan.update(version=3,kind='no_actuator_registration_input_path',expected_flash_generation=49,expected_full_flash_sha256=b['full_flash_sha256'],baseline_proof_sha256=digest(ready),input_forwarding='actual_readonly_xinput',receive_timeout_seconds=.060,observer_limit=32768,input_change_limit=128,pico_input_ack_available=False)
    for n in ('registration_policy_g49.py','run_registration_g49.py','registration_input_probe.py','phase_gap_probe_v2.py','phase_gap_validation_v2.py'):
        plan['source_sha256'][n]=digest(ROOT/'tools'/n)
    return plan

def validate_plan(plan):
    if plan!=build_plan():raise ValueError('Registration49 plan/source mismatch')
