"""Recovered accepted GAP42 runtime, bound only to current verified51 Flash."""
import json
from fidelity_game_policy_gap42 import ROOT,digest,build_game_plan as previous_plan,GameSession,can_click,game_child_passed,game_parent_passed

def build_game_plan():
    plan=previous_plan();ready=ROOT/'docs'/'V043_READY_BASELINE_20261028-214331.json';b=json.loads(ready.read_text())
    if b['baseline_generation']!=51 or b['previous_generation']!=50 or not b['physical_full_readback_verified'] or not b['outside_journal_unchanged'] or b['flash_write'] or b['firmware_sha256']!=plan['firmware_sha256']:raise ValueError('Verified51 required')
    for r in json.loads((ROOT/'docs/FIDELITY_GAP42_RUN_FREEZE_20261027-234740.json').read_text())['files']:
        if digest(ROOT/r['path'])!=r['sha256']:raise ValueError('Accepted runtime freeze mismatch')
    plan.update(version=10,expected_flash_generation=51,expected_full_flash_sha256=b['full_flash_sha256'],baseline_proof_sha256=digest(ready),scope='Recovered accepted GAP42 PC runtime, current51 binding only; restoration is not a new hardware acceptance.')
    for n in ('fidelity_game_policy_recovered51.py','run_fidelity_game_recovered51.py','assess_fidelity_game_recovered51.py'):
        plan['tool_sha256'][n]=digest(ROOT/'tools'/n)
    return plan

def validate_game_plan(plan):
    if plan!=build_game_plan():raise ValueError('Recovered51 plan or source mismatch')
