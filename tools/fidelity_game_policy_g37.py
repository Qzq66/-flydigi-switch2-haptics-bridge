"""Independent generation37 binding; unchanged accepted rendering and limits."""
import json
from fidelity_game_policy import ROOT,digest,build_game_plan as previous_plan,GameSession,game_child_passed,game_parent_passed,can_click

def build_game_plan():
    plan=previous_plan();docs=ROOT/'docs'
    ready=docs/'V043_READY_BASELINE_20261026-205500.json'
    baseline=json.loads(ready.read_text())
    if (baseline.get('status')!='V043_FLASH_READY_VERIFIED' or baseline.get('baseline_generation')!=37
        or baseline.get('physical_full_readback_verified') is not True or baseline.get('flash_write') is not False
        or baseline.get('firmware_sha256')!=plan['firmware_sha256']):raise ValueError('Verified37 baseline required')
    evidence=['RAM_PACING_ASSESSMENT_20261026-222940.json','RAM_PACING_RTT_20261026-222940.json','RAM_PACING_PATH_20261026-222940.json']
    proof,timing,run=[json.loads((docs/n).read_text()) for n in evidence]
    if proof['status']!='PASSED_BOUNDED_PACING_AND_CLEANUP' or not all(proof['checks'].values()):raise ValueError('Pacing cleanup evidence required')
    if timing['status']!='COMPLETE_ORIGINAL_REQUEST_TIMING_OFFLINE' or timing['sample_count']!=5218 or timing['receive_intervals']['over_80ms'] or timing['round_trip']['over_80ms']:raise ValueError('Bounded timing evidence required')
    if not run['full_flash_before_matches'] or not run['full_flash_after_matches']:raise ValueError('Unchanged physical Flash required')
    if timing['trace_sha256']!=run['packet_clock']['private_trace_sha256']:raise ValueError('Timing binding')
    plan.update(version=5,expected_flash_generation=37,expected_full_flash_sha256=baseline['full_flash_sha256'],baseline_proof_sha256=digest(ready),
        pacing_evidence_sha256={n:digest(docs/n) for n in evidence},heartbeat_gap_accepted_as_realtime=False,
        scope='Independent G37 one-episode game test following bounded idle timing; no realtime waiver. Fault is latched and never replayed.')
    for name in ('fidelity_game_policy_g37.py','run_fidelity_game_g37.py','assess_fidelity_game_g37.py'):
        plan['tool_sha256'][name]=digest(ROOT/'tools'/name)
    return plan

def validate_game_plan(plan):
    if plan!=build_game_plan():raise ValueError('G37 plan or bound sources changed')
