"""G42 diagnostic candidate: unchanged output, adds bounded phase observations."""
import json
from fidelity_game_policy_pcm41 import ROOT,digest,build_game_plan as previous_plan,GameSession,can_click
from fidelity_game_policy_pcm41 import game_child_passed as base_child_passed,game_parent_passed as base_parent_passed
from phase_gap_validation import assess_phase_gap

def build_game_plan():
    plan=previous_plan();docs=ROOT/'docs'
    ready=docs/'V043_READY_BASELINE_20261027-222357.json'
    specific=docs/'FIDELITY_PCM_SUBMISSION_ASSESSMENT_20261027-221627.json'
    analysis=docs/'PCM_POSTMUTE_GAP_ANALYSIS_2026-10-27.json'
    frozen=docs/'FIDELITY_PCM_RUN_FREEZE_20261027-221627.json'
    b=json.loads(ready.read_text());p=json.loads(specific.read_text());a=json.loads(analysis.read_text())
    if (b['status']!='V043_FLASH_READY_VERIFIED' or b['baseline_generation']!=42 or b['previous_generation']!=41 or not b['physical_full_readback_verified']
        or not b['outside_journal_unchanged'] or b['flash_write'] or b['firmware_sha256']!=plan['firmware_sha256']):raise ValueError('Verified42 baseline required')
    if p['status']!='PASSED_PCM_SUBMISSION_MATCH_AND_POSTMUTE_CLEANUP_GAME_STILL_INCOMPLETE' or p['strict_game_status']!='INCOMPLETE' or not all(p['checks'].values()):raise ValueError('Preserved PCM success and game fault evidence required')
    if a['status']!='COMPLETED_READONLY_POSTMUTE_GAP_ANALYSIS_NOT_GAME_PASS' or not all(a['checks'].values()):raise ValueError('Bounded gap analysis required')
    for row in json.loads(frozen.read_text())['files']:
        if digest(ROOT/row['path'])!=row['sha256']:raise ValueError('Frozen PCM runtime source/evidence changed')
    plan.update(version=9,expected_flash_generation=42,expected_full_flash_sha256=b['full_flash_sha256'],baseline_proof_sha256=digest(ready),
        pcm_specialist_assessment_sha256=digest(specific),gap_analysis_sha256=digest(analysis),previous_strict_game_status='INCOMPLETE',
        phase_observation=dict(max_events=65536,ring_rows=128,contexts=8,pre_rows=16,post_rows=8,max_compact_snapshot_bytes=262144,
            gap_trigger_seconds=.040,pause_trigger_seconds=.012,collector_requested_pause_seconds=.004,underlying_receive_timeout_seconds=.060),
        scope='One limited game diagnostic with bounded phase/max-gap contexts; no timeout or output changes and no realtime waiver.')
    for name in ('fidelity_game_policy_gap42.py','run_fidelity_game_gap42.py','assess_fidelity_game_gap42.py','phase_gap_probe.py','phase_gap_validation.py'):
        plan['tool_sha256'][name]=digest(ROOT/'tools'/name)
    return plan

def validate_game_plan(plan):
    if plan!=build_game_plan():raise ValueError('Gap42 plan or bound sources changed')

def game_child_passed(child):
    return base_child_passed(child) and assess_phase_gap(child)['passed']

def game_parent_passed(program,plan):
    return base_parent_passed(program,plan) and game_child_passed(program.get('child',{}))
