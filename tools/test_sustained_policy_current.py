"""Offline tests for the current-baseline rebound plan (no device access)."""
import json
import unittest
from unittest import mock

import dispatch_windows_profile_current as profile
import sustained_game_policy_current as policy


class Tests(unittest.TestCase):
    def test_plan_is_bound_to_the_install_record(self):
        record = policy._record()
        plan = policy.build_game_plan()
        self.assertEqual(plan['expected_flash_generation'], record['baseline_generation'])
        self.assertEqual(plan['expected_full_flash_sha256'], record['installed_snapshot_sha256'])
        self.assertIn('sustained_game_policy_current.py', plan['tool_sha256'])
        self.assertIn('run_sustained_game_current.py', plan['tool_sha256'])

    def test_protocol_budget_is_unchanged(self):
        plan = policy.build_game_plan()
        self.assertEqual(plan['multi_event']['maximum_events'], 6)
        self.assertEqual(plan['multi_event']['output_seconds'], 60)
        self.assertEqual(plan['multi_event']['frame_limit'], 7500)
        self.assertEqual(plan['limits']['maximum_armed_seconds'], 60.25)

    def test_plan_survives_json_round_trip(self):
        plan = policy.build_game_plan()
        self.assertEqual(json.loads(json.dumps(plan)), plan)
        policy.validate_game_plan(json.loads(json.dumps(plan)))

    def test_tampered_plan_is_rejected(self):
        plan = policy.build_game_plan()
        plan['expected_flash_generation'] += 1
        with self.assertRaises(ValueError):
            policy.validate_game_plan(plan)

    def test_unknown_install_generation_is_rejected(self):
        record = dict(policy._record(), baseline_generation=999,
                      installed_snapshot_sha256='0' * 64)
        with mock.patch.object(policy, '_record', return_value=record):
            with self.assertRaises(ValueError):
                policy.build_game_plan()

    def test_adapter_profile_binds_the_priority_window(self):
        plan = profile.build_game_plan()
        self.assertEqual(plan['entry_variant'],
                         'async-phase-adapter-v3-current-baseline-priority-window')
        self.assertEqual(plan['dispatch_priority_window']['level'], 'TIME_CRITICAL')
        self.assertTrue(plan['dispatch_priority_window']['restore_on_exit'])
        for name in ('priority_window.py', 'thread_priority.py', 'dispatch_windows_entry.py'):
            self.assertIn(name, plan['tool_sha256'])
        profile.validate_game_plan(plan)

    def test_adapter_plan_rejects_a_dropped_priority_module(self):
        plan = profile.build_game_plan()
        del plan['tool_sha256']['priority_window.py']
        with self.assertRaises(ValueError):
            profile.validate_game_plan(plan)


if __name__ == '__main__':
    unittest.main()
