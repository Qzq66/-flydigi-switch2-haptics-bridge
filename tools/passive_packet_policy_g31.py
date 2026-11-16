"""Generation31 diagnostic only; bind the verified journal and clock observer."""
import json
from passive_reply_policy_g30 import ROOT,digest,build_plan as previous_plan,PassiveSession,collection_completed

def build_plan():
    plan=previous_plan();ready=ROOT/'docs/V043_READY_BASELINE_20261025-203921.json'
    proof=ROOT/'docs/PASSIVE_REPLY_ASSESSMENT_20261025-203103.json'
    baseline=json.loads(ready.read_text());assessment=json.loads(proof.read_text())
    if (baseline.get('baseline_generation')!=31 or baseline.get('physical_full_readback_verified') is not True
        or baseline.get('flash_write') is not False or baseline.get('firmware_sha256')!=plan['firmware_sha256']):
        raise ValueError('Verified generation31 required')
    if assessment.get('generation')!=31 or not all(assessment.get('checks',{}).values()) or len(assessment.get('checks',{}))!=26:
        raise ValueError('Previous same-trial assessment required')
    for name,h in assessment['source_sha256'].items():
        if digest(ROOT/name)!=h:raise ValueError('Previous source changed: '+name)
    plan.update(version=8,kind='no_actuator_component_and_application_packet_clock',expected_flash_generation=31,
        expected_full_flash_sha256=baseline['full_flash_sha256'],baseline_proof_sha256=digest(ready),
        recovery_proof_sha256=digest(proof),packet_trace_limit=100000,packet_snapshot_bytes=256,
        packet_log_limit_mb=128,packet_capture_seconds=270,adopt_into_game_output=False)
    for name in ('passive_packet_policy_g31.py','run_passive_packet_g31.py','packet_clock_probe.py','capture_clock.py'):
        plan['source_sha256'][name]=digest(ROOT/'tools'/name)
    return plan

def validate_plan(plan):
    if plan!=build_plan():raise ValueError('G31 packet observation plan changed')
