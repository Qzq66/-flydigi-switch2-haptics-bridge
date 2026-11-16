"""Current-baseline runner: the frozen g61 runner rebound to the current verified baseline.

No live logic is duplicated or edited here.  The frozen runner is imported as a private
module and its plan binding, pass predicates and `__file__` are rebound so that:
  * `--prepare` writes a plan bound to whatever baseline the install record proves;
  * `--child` validates that plan with the current policy;
  * the parent spawns this file as its child, which reapplies the same rebinding.
"""
import pathlib
import run_sustained_game_g61 as _base
import sustained_game_policy_current as _policy

_base.build_game_plan = _policy.build_game_plan
_base.validate_game_plan = _policy.validate_game_plan
_base.game_child_passed = _policy.game_child_passed
_base.game_parent_passed = _policy.game_parent_passed
_base.GameSession = _policy.GameSession
_base.__file__ = str(pathlib.Path(__file__).absolute())


def main():
    return _base.main()


if __name__ == '__main__':
    raise SystemExit(main())
