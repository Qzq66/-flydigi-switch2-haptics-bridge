"""Independent12ms limited game candidate bound to verified57."""
import json
from fidelity_game_policy_gap42 import ROOT,digest,build_game_plan as previous_plan,GameSession,can_click,game_child_passed,game_parent_passed

def build_game_plan():
    plan=previous_plan();ready=ROOT/'docs'/'V043_READY_BASELINE_20261029-232236.json';b=json.loads(ready.read_text())
    if b['baseline_generation']!=57 or b['previous_generation']!=55 or not b['physical_full_readback_verified'] or not b['outside_journal_unchanged'] or b['flash_write'] or b['firmware_sha256']!=plan['firmware_sha256']:raise ValueError('Verified57 required')
    for r in json.loads((ROOT/'docs/FIDELITY_GAP42_RUN_FREEZE_20261027-234740.json').read_text())['files']:
        if digest(ROOT/r['path'])!=r['sha256']:raise ValueError('Accepted runtime freeze mismatch')
    plan.update(version=12,expected_flash_generation=57,expected_full_flash_sha256=b['full_flash_sha256'],baseline_proof_sha256=digest(ready),scope='Recovered accepted GAP42 PC runtime, current57 binding and12ms receive budget only; not hardware accepted.')
    for n in ('fidelity_game_policy_receive12_g57.py','run_fidelity_game_receive12_g57.py','assess_fidelity_game_receive12_g57.py'):
        plan['tool_sha256'][n]=digest(ROOT/'tools'/n)
    plan['phase_observation']['underlying_receive_timeout_seconds']=.012
    plan['receive_budget_seconds']=.012
    plan['default_game_replaced']=False
    plan['tool_sha256']['receive_budget12_transport.py']=digest(ROOT/'tools/receive_budget12_transport.py')
    return plan

def validate_game_plan(plan):
    if plan!=build_game_plan():raise ValueError('Receive12G57 plan or source mismatch')
