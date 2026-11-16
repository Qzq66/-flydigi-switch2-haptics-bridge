"""Independent generation38 repeat binding; unchanged G37 rendering and guards."""
import json
from fidelity_game_policy_g37 import ROOT,digest,build_game_plan as previous_plan,GameSession,game_child_passed,game_parent_passed,can_click

def build_game_plan():
    plan=previous_plan();docs=ROOT/'docs'
    ready=docs/'V043_READY_BASELINE_20261026-232833.json'
    assessment=docs/'FIDELITY_GAME_G37_ASSESSMENT_20261026-232226.json'
    frozen=docs/'FIDELITY_GAME_G37_RUN_FREEZE_20261026-232226.json'
    baseline=json.loads(ready.read_text());prior=json.loads(assessment.read_text())
    if (baseline.get('status')!='V043_FLASH_READY_VERIFIED' or baseline.get('baseline_generation')!=38
        or baseline.get('previous_generation')!=37 or baseline.get('physical_full_readback_verified') is not True
        or baseline.get('outside_journal_unchanged') is not True or baseline.get('flash_write') is not False
        or baseline['firmware_sha256']!=plan['firmware_sha256']):raise ValueError('Verified38 baseline required')
    if (prior.get('status')!='PASSED_SINGLE_SWITCH_GAME_DUAL_BAND_CANDIDATE' or prior.get('journal_generation')!=38
        or not all(prior['checks'].values()) or len(prior['checks'])!=16):raise ValueError('Full G37 acceptance required')
    for row in json.loads(frozen.read_text())['files']:
        if digest(ROOT/row['path'])!=row['sha256']:raise ValueError('Frozen success evidence changed')
    plan.update(version=6,expected_flash_generation=38,expected_full_flash_sha256=baseline['full_flash_sha256'],baseline_proof_sha256=digest(ready),
        previous_game_acceptance_sha256=digest(assessment),previous_success_freeze_sha256=digest(frozen),
        scope='Independent G38 same-scene repeat of accepted G37 single episode; all timing and output limits unchanged.')
    for name in ('fidelity_game_policy_g38.py','run_fidelity_game_g38.py','assess_fidelity_game_g38.py'):
        plan['tool_sha256'][name]=digest(ROOT/'tools'/name)
    return plan

def validate_game_plan(plan):
    if plan!=build_game_plan():raise ValueError('G38 plan or bound sources changed')
