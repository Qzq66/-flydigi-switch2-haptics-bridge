"""Generation44 candidate: existing transport RTT retained; guards unchanged."""
import json
from fidelity_game_policy_gap42 import ROOT,digest,build_game_plan as previous_plan,GameSession,can_click
from fidelity_game_policy_gap42 import game_child_passed as base_child_passed,game_parent_passed as base_parent_passed
from phase_gap_validation_v2 import assess_phase_gap

def build_game_plan():
    plan=previous_plan();docs=ROOT/'docs'
    ready=docs/'V043_READY_BASELINE_20261028-200603.json'
    b=json.loads(ready.read_text())
    if (b['status']!='V043_FLASH_READY_VERIFIED' or b['baseline_generation']!=44 or b['previous_generation']!=43
        or not b['physical_full_readback_verified'] or not b['outside_journal_unchanged'] or b['flash_write']
        or b['firmware_sha256']!=plan['firmware_sha256']):raise ValueError('Verified44 baseline required')
    for r in json.loads((docs/'FIDELITY_GAP42_RUN_FREEZE_20261027-234740.json').read_text())['files']:
        if digest(ROOT/r['path'])!=r['sha256']:raise ValueError('Frozen previous runtime changed')
    plan.update(version=10,expected_flash_generation=44,expected_full_flash_sha256=b['full_flash_sha256'],baseline_proof_sha256=digest(ready),
        rtt_observation=dict(schema_version=2,existing_timer_starts_after_send=True,timeout_rtt_invented=False),
        scope='One limited game with bounded existing RTT split; no mapping, transport or guard changes.')
    for name in ('phase_gap_probe_v2.py','phase_gap_validation_v2.py','fidelity_game_policy_rtt44.py','run_fidelity_game_rtt44.py','assess_fidelity_game_rtt44.py'):
        plan['tool_sha256'][name]=digest(ROOT/'tools'/name)
    return plan

def validate_game_plan(plan):
    if plan!=build_game_plan():raise ValueError('RTT44 plan or sources changed')

def game_child_passed(child):return base_child_passed(child) and assess_phase_gap(child)['passed']
def game_parent_passed(program,plan):return base_parent_passed(program,plan) and game_child_passed(program.get('child',{}))
