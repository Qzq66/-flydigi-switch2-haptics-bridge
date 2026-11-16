"""Generation32 two-component diagnostic candidate, no game or motor adoption."""
import json
from passive_packet_policy_g31 import ROOT,digest,build_plan as previous_plan,PassiveSession,collection_completed

def build_plan():
    plan=previous_plan()
    ready=ROOT/'docs/V043_READY_BASELINE_20261025-221331.json'
    proof=ROOT/'docs/PASSIVE_PACKET_RETRY_ASSESSMENT_20261025-220337.json'
    baseline=json.loads(ready.read_text());prior=json.loads(proof.read_text())
    if (baseline.get('baseline_generation')!=32 or baseline.get('previous_generation')!=31
        or baseline.get('physical_full_readback_verified') is not True or baseline.get('flash_write') is not False
        or baseline.get('firmware_sha256')!=plan['firmware_sha256']):raise ValueError('Verified32 baseline required')
    if (prior.get('generation')!=32 or len(prior.get('checks',{}))!=25 or not all(prior['checks'].values())
        or prior.get('adopt_into_game_output') is not False or prior.get('complete_component_coverage') is not False):raise ValueError('Previous partial result must remain qualified')
    for name,h in prior['source_sha256'].items():
        if digest(ROOT/name)!=h:raise ValueError('Previous source changed: '+name)
    plan.update(version=9,kind='no_actuator_two_hotspot_components_original_adjacent_correlation',expected_flash_generation=32,
        expected_full_flash_sha256=baseline['full_flash_sha256'],baseline_proof_sha256=digest(ready),recovery_proof_sha256=digest(proof),
        capture_component_selection='fresh_active_hotspot_TCPIP_and_WFP_8023_only',capture_component_count=2,
        command_control_timeout_seconds=5,offline_conversion_timeout_seconds=45,minimum_host_power_before_recovery_seconds=190,
        require_complete_application_receive_coverage=True,adjacent_original_application_rows_only=True)
    for name in ('passive_packet_policy_g32.py','run_passive_packet_g32.py','run_pktmon_passive_g32.ps1','pktmon_capture_common_v4.ps1','component_receive_analysis_v2.py','usb_recovery_clock.py'):
        plan['source_sha256'][name]=digest(ROOT/'tools'/name)
    return plan

def validate_plan(plan):
    if plan!=build_plan():raise ValueError('G32 plan/source mismatch')
