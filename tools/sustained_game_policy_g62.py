"""Independent 60-second six-event candidate bound to verified generation 62.

The frozen generation-61 policy cannot run against the current baseline: it requires a proof
whose `baseline_generation` is 61, while the accepted baseline is now 62.  This module keeps
every inherited rule (8 ms grid, 4 ms gate, 80 ms guard, six events, 7 500 frames) and only
rebinds the baseline proof, the expected generation and the new tool digests.  It builds a
plan offline; it never opens a device.
"""
import json
from fidelity_game_policy_gap42 import ROOT, digest
import sustained_game_policy_g61 as g61

READY = ROOT / 'docs' / 'V043_READY_BASELINE_20261115-170226.json'
GameSession = g61.GameSession
game_child_passed = g61.game_child_passed


def build_game_plan():
    plan = g61.build_game_plan()
    baseline = json.loads(READY.read_text())
    if (baseline['baseline_generation'] != 62 or baseline['previous_generation'] != 61
            or not baseline['physical_full_readback_verified']
            or not baseline['outside_journal_unchanged'] or baseline['flash_write']
            or baseline['firmware_sha256'] != plan['firmware_sha256']):
        raise ValueError('Verified62 required')
    plan.update(expected_flash_generation=62,
                expected_full_flash_sha256=baseline['full_flash_sha256'],
                baseline_proof_sha256=digest(READY),
                scope='Generation62 rebound candidate; single variable is the dispatch priority window; not hardware validated.')
    for name in ('sustained_game_policy_g62.py', 'run_sustained_game_g62.py'):
        plan['tool_sha256'][name] = digest(ROOT / 'tools' / name)
    return plan


def validate_game_plan(plan):
    if plan != build_game_plan():
        raise ValueError('SustainedG62 plan or source mismatch')


def game_parent_passed(parent, plan):
    return g61.game_parent_passed(parent, plan)
