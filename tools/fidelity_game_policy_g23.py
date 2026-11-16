"""Independent generation23 binding; previous game/passive sources stay frozen."""
import json
from fidelity_game_policy import (ROOT,digest,build_game_plan as previous_plan,
    GameSession,game_child_passed,game_parent_passed,can_click)

def build_game_plan():
    plan=previous_plan();docs=ROOT/'docs'
    ready=docs/'V043_READY_BASELINE_20261025-161622.json'
    acceptance=docs/'PASSIVE_TRANSPORT_ASSESSMENT_20261025-160907.json'
    baseline=json.loads(ready.read_text());proof=json.loads(acceptance.read_text())
    if (baseline.get('status')!='V043_FLASH_READY_VERIFIED' or baseline.get('baseline_generation')!=23
        or baseline.get('previous_generation')!=22 or baseline.get('physical_full_readback_verified') is not True
        or baseline.get('outside_journal_unchanged') is not True or baseline.get('flash_write') is not False
        or baseline.get('firmware_sha256')!=plan['firmware_sha256']):raise ValueError('Verified generation23 baseline required')
    if (proof.get('status')!='PASSED_PASSIVE_TRANSPORT_AND_PERSISTENT_JOURNAL_WITH_TIMING_GAP'
        or len(proof.get('checks',{}))!=18 or not all(proof['checks'].values())
        or proof.get('journal_generation')!=23):raise ValueError('Complete passive same-trial journal proof required')
    for name,h in proof['source_sha256'].items():
        if digest(ROOT/name)!=h:raise ValueError('Passive evidence changed: '+name)
    capture=json.loads((docs/'V043_HOST_CAPTURE_20261025-161532.json').read_text())
    if capture['full_flash_sha256']!=baseline['full_flash_sha256']:raise ValueError('Baseline/capture mismatch')
    plan.update(version=4,expected_flash_generation=23,expected_full_flash_sha256=baseline['full_flash_sha256'],
        baseline_proof_sha256=digest(ready),passive_transport_assessment_sha256=digest(acceptance),
        heartbeat_gap_accepted_as_realtime=False,
        scope='Independent G23 one-episode game test; fault stops output permanently but confirmed-stop collection continues. Not an 80ms stability waiver.')
    for name in ('fidelity_game_policy_g23.py','run_fidelity_game_g23.py','assess_fidelity_game_g23.py'):
        plan['tool_sha256'][name]=digest(ROOT/'tools'/name)
    return plan

def validate_game_plan(plan):
    if plan!=build_game_plan():raise ValueError('G23 plan, passive proof or bound source changed')
