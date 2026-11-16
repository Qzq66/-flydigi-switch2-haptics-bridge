"""No-actuator registration input diagnostic bound to verified generation53."""
import json
from passive_transport_policy import ROOT,digest,build_plan as previous_plan,PassiveSession,collection_completed as previous_completed

def build_plan():
    plan=previous_plan();ready=ROOT/'docs'/'V043_READY_BASELINE_20261028-223410.json';b=json.loads(ready.read_text())
    if b['baseline_generation']!=53 or b['previous_generation']!=52 or not b['physical_full_readback_verified'] or not b['outside_journal_unchanged'] or b['flash_write'] or b['firmware_sha256']!=plan['firmware_sha256']:raise ValueError('Verified53 required')
    plan.update(version=5,kind='no_actuator_registration_input_path',expected_flash_generation=53,expected_full_flash_sha256=b['full_flash_sha256'],baseline_proof_sha256=digest(ready),input_forwarding='actual_readonly_xinput',receive_timeout_seconds=.060,observer_limit=32768,input_change_limit=128,pico_input_ack_available=False)
    for n in ('call_breakdown_policy_g53.py','run_call_breakdown_g53.py','poll_call_breakdown.py','poll_call_breakdown_validation.py','phase_gap_probe.py','phase_gap_validation.py'):
        plan['source_sha256'][n]=digest(ROOT/'tools'/n)
    return plan

def validate_plan(plan):
    if plan!=build_plan():raise ValueError('CallBreakdown53 plan/source mismatch')

from poll_call_breakdown_validation import assess_breakdown
from phase_gap_validation import assess_phase_gap
def collection_completed(report):
    return previous_completed(report) and assess_breakdown(report)['passed'] and assess_phase_gap(report)['passed']
