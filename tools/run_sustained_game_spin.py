"""Spin-wait candidate runner: the frozen g61 driver with the loop wait replaced.

Everything except the child loop is the frozen driver: `play()` still performs the BOOTSEL
preflight, hotspot gate, PC input liveness window, discovery, the Tk arm window and the
guardian.  Only `sustained_game_spin_child.child` runs the loop, and inside it the single
`time.sleep(.001)` became `wait(game)`.  Enable with FLYDIGI_SPIN_WAIT=1.

Two observation levers ride along, both off by default:
  FLYDIGI_LOOP_PROBE=1  measures the loop-body budget (tick entry lateness, gap, publish cost)
  FLYDIGI_ASYNC_PHASE=1 publishes the phase file from one writer thread instead of the loop
"""
import json
import pathlib
import sys

import run_sustained_game_g61 as _base
import async_phase_path
import loop_probe_session
from sustained_game_policy_current import (build_game_plan, game_child_passed,
                                           game_parent_passed, validate_game_plan, GameSession)
from sustained_game_spin_child import child as _spin_child, spin_stats

_base.build_game_plan = build_game_plan
_base.validate_game_plan = validate_game_plan
_base.GameSession = GameSession
_base.game_child_passed = game_child_passed
_base.game_parent_passed = game_parent_passed
_base.__file__ = str(pathlib.Path(__file__).resolve())


def child(*args):
    # index 2 is the child report, index 3 the phase path handed to the frozen loop.
    arguments = list(args)
    writer = None
    if len(arguments) == 5:
        if loop_probe_session.enabled():
            arguments[3] = loop_probe_session.ProbePath(arguments[3])
        if async_phase_path.enabled():
            writer = async_phase_path.AsyncPhasePath(arguments[3])
            arguments[3] = writer
    try:
        code = _spin_child(*arguments)
    finally:
        if writer is not None:
            writer.close()
    if len(arguments) == 5 and loop_probe_session.enabled():
        try:
            report = json.loads(pathlib.Path(arguments[2]).read_text())
            report['publish_probe'] = loop_probe_session.publish_stats()
            if writer is not None:
                report['async_phase_writer'] = writer.stats()
            pathlib.Path(arguments[2]).write_text(json.dumps(report, indent=2))
        except (OSError, ValueError):
            pass
    return code


def main():
    _base.child = child
    code = _base.main()
    print('SPIN_WAIT:' + repr(spin_stats()), file=sys.stderr, flush=True)
    if async_phase_path.enabled():
        print('ASYNC_PHASE:enabled', file=sys.stderr, flush=True)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
