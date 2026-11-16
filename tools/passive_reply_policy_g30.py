"""Generation30 no-actuator request/reply provenance observation."""
import json
from passive_short_wait_policy_g29 import ROOT,digest,build_plan as previous_plan,PassiveSession,collection_completed

def build_plan():
    plan=previous_plan();docs=ROOT/'docs'
    ready=docs/'V043_READY_BASELINE_20261025-202200.json'
    proof_path=docs/'PASSIVE_SHORT_WAIT_ASSESSMENT_20261025-201439.json'
    baseline=json.loads(ready.read_text());proof=json.loads(proof_path.read_text())
    if (baseline.get('status')!='V043_FLASH_READY_VERIFIED' or baseline.get('baseline_generation')!=30
        or baseline.get('previous_generation')!=29 or baseline.get('physical_full_readback_verified') is not True
        or baseline.get('outside_journal_unchanged') is not True or baseline.get('flash_write') is not False
        or baseline.get('firmware_sha256')!=plan['firmware_sha256']):raise ValueError('Verified generation30 installation required')
    if (proof.get('status')!='PASSED_NO_ACTUATOR_SHORT_RECEIVE_DATA_INTEGRITY_COMPARISON' or proof.get('generation')!=30
        or len(proof.get('checks',{}))!=25 or not all(proof['checks'].values())
        or proof.get('adopt_into_game_output') is not False):raise ValueError('Diagnostic-only previous comparison required')
    for name,h in proof['source_sha256'].items():
        if digest(ROOT/name)!=h:raise ValueError('Previous comparison changed: '+name)
    capture=json.loads((docs/'V043_HOST_CAPTURE_20261025-202023.json').read_text())
    if capture['full_flash_sha256']!=baseline['full_flash_sha256']:raise ValueError('Generation30 snapshot differs')
    plan.update(version=7,kind='no_actuator_original_request_reply_age_observation',expected_flash_generation=30,
        expected_full_flash_sha256=baseline['full_flash_sha256'],baseline_proof_sha256=digest(ready),
        recovery_proof_sha256=digest(proof_path),reference_measurement_generation=30,
        adopt_into_game_output=False,request_history_limit=512,reply_history_limit=64,
        late_reply_history_limit=32,observer_changes_packet_acceptance=False,board_telemetry_over_udp=False)
    for name in ('passive_reply_policy_g30.py','run_passive_reply_g30.py','reply_provenance_probe.py'):
        plan['source_sha256'][name]=digest(ROOT/'tools'/name)
    return plan

def validate_plan(plan):
    if plan!=build_plan():raise ValueError('G30 reply-provenance plan or sources changed')
