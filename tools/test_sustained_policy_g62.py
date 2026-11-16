"""Offline tests for the generation-62 rebound plan (no device access)."""
import json
import unittest
import dispatch_windows_profile_g62 as profile
import sustained_game_policy_g62 as policy


class Tests(unittest.TestCase):
    def test_plan_is_bound_to_generation_62(self):
        plan = policy.build_game_plan()
        baseline = json.loads(policy.READY.read_text())
        self.assertEqual(plan['expected_flash_generation'], 62)
        self.assertEqual(plan['expected_full_flash_sha256'], baseline['full_flash_sha256'])
        self.assertEqual(plan['baseline_proof_sha256'], policy.digest(policy.READY))
        self.assertEqual(plan['firmware_sha256'], baseline['firmware_sha256'])
        self.assertIn('sustained_game_policy_g62.py', plan['tool_sha256'])
        self.assertIn('run_sustained_game_g62.py', plan['tool_sha256'])

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
        plan['expected_flash_generation'] = 61
        with self.assertRaises(ValueError):
            policy.validate_game_plan(plan)

    def test_adapter_profile_binds_the_priority_window(self):
        plan = profile.build_game_plan()
        self.assertEqual(plan['entry_variant'], 'async-phase-adapter-v2-priority-window')
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
