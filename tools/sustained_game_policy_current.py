"""Candidate bound to whichever baseline the install record proves.

The historical policies each freeze one generation's proof, so every new baseline needs a
new module.  This policy binds the plan to the *current* verified baseline instead: it
reads the private install record (generation plus installed snapshot digest), finds the
public `V043_READY_BASELINE_*` proof whose generation and full-flash digest match that
record, and requires that proof to be a contiguous, physically read-back, journal-preserving,
never-flashed baseline of this firmware.

Every inherited rule (8 ms grid, 4 ms gate, 80 ms guard, six events, 7 500 frames) still
comes from the frozen generation-61 plan; only the baseline binding, the expected generation
and the tool digests are replaced.  The plan is built offline; no device is opened.
"""
import json
import pathlib
from fidelity_game_policy_gap42 import ROOT, digest
import sustained_game_policy_g61 as g61
import priority_game_session
import loop_probe_session

SELECTION = ROOT / 'handoff' / '2026-10-22' / 'work' / 'private' / 'v043-install-selection.json'
GameSession = loop_probe_session.wrap(priority_game_session.wrap(g61.GameSession))
game_child_passed = g61.game_child_passed
PROOF_FIELDS = ('baseline_generation', 'previous_generation', 'full_flash_sha256',
                'firmware_sha256', 'physical_full_readback_verified',
                'outside_journal_unchanged', 'flash_write')


def _record():
    pointer = json.loads(SELECTION.read_text())
    return json.loads(pathlib.Path(pointer['record']).read_text())


def _baseline(plan):
    record = _record()
    generation = int(record['baseline_generation'])
    full = record['installed_snapshot_sha256']
    matches = []
    for path in sorted((ROOT / 'docs').glob('V043_READY_BASELINE_*.json')):
        try:
            proof = json.loads(path.read_text())
        except ValueError:
            continue
        if (proof.get('baseline_generation') == generation
                and proof.get('full_flash_sha256') == full):
            matches.append((path, proof))
    if not matches:
        raise ValueError('Public verified baseline proof required for the install record')
    matches.sort(key=lambda item: item[0].stat().st_mtime)
    path, proof = matches[-1]
    # Duplicate proofs of the same generation must not disagree about the security fields.
    for _, other in matches[:-1]:
        if any(other.get(field) != proof.get(field) for field in PROOF_FIELDS):
            raise ValueError('Ambiguous public proofs for one install record')
    if (proof['previous_generation'] != generation - 1
            or not proof['physical_full_readback_verified']
            or not proof['outside_journal_unchanged'] or proof['flash_write']
            or proof['firmware_sha256'] != plan['firmware_sha256']):
        raise ValueError('Verified%d required' % generation)
    return generation, path, proof


def build_game_plan():
    plan = g61.build_game_plan()
    generation, path, proof = _baseline(plan)
    plan.update(expected_flash_generation=generation,
                expected_full_flash_sha256=proof['full_flash_sha256'],
                baseline_proof_sha256=digest(path),
                scope=('Generation%d rebound candidate; single variable is the dispatch '
                       'priority window; not hardware validated.' % generation))
    for name in ('sustained_game_policy_current.py', 'run_sustained_game_current.py'):
        plan['tool_sha256'][name] = digest(ROOT / 'tools' / name)
    return plan


def validate_game_plan(plan):
    if plan != build_game_plan():
        raise ValueError('SustainedCurrent plan or source mismatch')


def game_parent_passed(parent, plan):
    return g61.game_parent_passed(parent, plan)
