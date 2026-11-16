"""Generation41 candidate adds post-write observation, unchanged renderer and guards."""
import json
from fidelity_game_policy_g40 import ROOT,digest,build_game_plan as previous_plan,GameSession,can_click
from fidelity_game_policy_g40 import game_child_passed as base_child_passed,game_parent_passed as base_parent_passed
from written_pcm_validation import assess_written

def build_game_plan():
    plan=previous_plan();docs=ROOT/'docs'
    ready=docs/'V043_READY_BASELINE_20261027-212936.json'
    accepted=docs/'FIDELITY_GAME_G40_ASSESSMENT_20261027-212240.json'
    frozen=docs/'FIDELITY_GAME_G40_RUN_FREEZE_20261027-212240.json'
    baseline=json.loads(ready.read_text());proof=json.loads(accepted.read_text())
    if (baseline['baseline_generation']!=41 or baseline['previous_generation']!=40 or not baseline['physical_full_readback_verified']
        or not baseline['outside_journal_unchanged'] or baseline['flash_write'] or baseline['firmware_sha256']!=plan['firmware_sha256']):raise ValueError('Verified41 baseline required')
    if proof['status']!='PASSED_SINGLE_SWITCH_GAME_DUAL_BAND_CANDIDATE' or proof['journal_generation']!=41 or not all(proof['checks'].values()):raise ValueError('Complete latest game proof required')
    for row in json.loads(frozen.read_text())['files']:
        if digest(ROOT/row['path'])!=row['sha256']:raise ValueError('Frozen game source/evidence changed')
    plan.update(version=8,expected_flash_generation=41,expected_full_flash_sha256=baseline['full_flash_sha256'],baseline_proof_sha256=digest(ready),
        written_pcm_observation=dict(frame_limit=1900,maximum_code_offset=12,maximum_squared_code_sum_per_side=8000,raw_pcm_storage=False,successful_host_submissions_only=True),
        previous_game_acceptance_sha256=digest(accepted),previous_success_freeze_sha256=digest(frozen),
        scope='One limited game episode with bounded post-writer PCM/report hashes; not controller receipt or physical fidelity.')
    for name in ('fidelity_game_policy_pcm41.py','run_fidelity_game_pcm41.py','assess_fidelity_game_pcm41.py','written_pcm_probe.py','written_pcm_validation.py','audit_game_parameter_mapping.py'):
        plan['tool_sha256'][name]=digest(ROOT/'tools'/name)
    return plan

def validate_game_plan(plan):
    if plan!=build_game_plan():raise ValueError('PCM41 plan or bound sources changed')

def game_child_passed(child):
    return base_child_passed(child) and assess_written(child)['passed']

def game_parent_passed(program,plan):
    return base_parent_passed(program,plan) and game_child_passed(program.get('child',{}))
