"""Generation36 diagnostic: remove only the capture IP condition."""
import json
from passive_packet_policy_g35 import ROOT,digest,build_plan as previous_plan,PassiveSession,collection_completed

def build_plan():
    plan=previous_plan();ready=ROOT/'docs/V043_READY_BASELINE_20261026-203018.json';proof=ROOT/'docs/PASSIVE_PACKET_G35_ASSESSMENT_20261026-202153.json'
    baseline=json.loads(ready.read_text());prior=json.loads(proof.read_text())
    if (baseline.get('baseline_generation')!=36 or baseline.get('previous_generation')!=35
        or baseline.get('physical_full_readback_verified') is not True or baseline.get('flash_write') is not False
        or baseline.get('firmware_sha256')!=plan['firmware_sha256']):raise ValueError('Verified36 baseline required')
    if (prior.get('generation')!=36 or len(prior.get('checks',{}))!=25 or not all(prior['checks'].values())
        or prior.get('captured_replies')!=0 or prior.get('adopt_into_game_output') is not False):raise ValueError('Previous missing-RX conclusion required')
    for name,h in prior['source_sha256'].items():
        if digest(ROOT/name)!=h:raise ValueError('Previous source changed: '+name)
    plan.update(version=11,kind='no_actuator_same_components_port_only_filter_comparison',expected_flash_generation=36,
        expected_full_flash_sha256=baseline['full_flash_sha256'],baseline_proof_sha256=digest(ready),previous_attempt_proof_sha256=digest(proof),
        capture_filter='UDP49724_without_IP_condition',controlled_change='remove_capture_IP_condition_only',adopt_into_game_output=False)
    for name in ('passive_packet_policy_g36.py','run_passive_packet_g36.py','run_pktmon_passive_g36.ps1'):
        plan['source_sha256'][name]=digest(ROOT/'tools'/name)
    return plan

def validate_plan(plan):
    if plan!=build_plan():raise ValueError('G36 plan/source mismatch')
