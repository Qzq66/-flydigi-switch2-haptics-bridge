"""Adapter profile bound to the generation-62 policy (priority-window candidate).

Same contract as `dispatch_windows_profile.py`, rebound to the 62 policy, and the plan
additionally binds the priority-window modules so a trial cannot silently drop the one
variable under test.
"""
from sustained_game_policy_g62 import ROOT, digest, build_game_plan as base_plan, game_child_passed as base_child_passed, game_parent_passed as base_parent_passed


def build_game_plan():
    plan = base_plan()
    plan['entry_variant'] = 'async-phase-adapter-v2-priority-window'
    plan['requires_separate_additional_trial_authorization'] = True
    for name in ('dispatch_windows_entry.py', 'dispatch_windows_profile_g62.py',
                 'dispatch_io_candidate.py', 'offline_phase_publisher.py',
                 'priority_window.py', 'thread_priority.py'):
        plan['tool_sha256'][name] = digest(ROOT / 'tools' / name)
    plan['dispatch_priority_window'] = dict(flag='--priority-window', level='TIME_CRITICAL',
                                            restore_on_exit=True, scope='armed dispatch step only')
    return plan


def validate_game_plan(plan):
    if plan != build_game_plan():
        raise ValueError('G62 adapter plan or source binding changed')


def child_passed(report):
    publisher = report.get('phase_publisher', {})
    probe = report.get('dispatch_io', {})
    observed = (probe.get('integration_scope') == 'Windows adapter candidate, not hardware accepted'
                and probe.get('first_fault') is None and probe.get('steps', 0) > 0
                and len(probe.get('recent', [])) <= 32)
    return (observed and publisher.get('written', 0) >= 1 and base_child_passed(report)
            and publisher.get('closed') is True and publisher.get('error') is None
            and publisher.get('pending_count') == 0 and not report.get('adapter_cleanup_errors'))


def parent_passed(report, plan):
    return base_parent_passed(report, plan) and child_passed(report.get('child', {}))
