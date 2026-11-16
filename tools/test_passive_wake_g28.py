import ast,unittest
from passive_wake_policy_g28 import ROOT,build_plan,validate_plan

class WakePlan(unittest.TestCase):
    def test_plan_uses_actual28_without_rewriting_prior_strict_result(self):
        plan=build_plan();validate_plan(plan)
        self.assertEqual(plan['expected_flash_generation'],28)
        self.assertFalse(plan['prior_strict_single_generation_passed']);self.assertFalse(plan['timing_policy_change'])
        self.assertEqual(plan['collector_sleep_request_seconds'],.004)
        with self.assertRaises(ValueError):validate_plan(dict(plan,prior_strict_single_generation_passed=True))

    def test_entry_has_no_actuator_and_only_observes_collector_pause(self):
        source=(ROOT/'tools/run_passive_wake_g28.py').read_text(encoding='utf-8');tree=ast.parse(source)
        calls={n.func.attr for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)}
        self.assertFalse(calls.intersection({'mode','stream','waveform','stop','arm'}))
        self.assertIn('pause=sleep_probe',source)
        self.assertNotIn('GameSession',source);self.assertNotIn('StreamSession',source)

if __name__=='__main__':raise SystemExit(unittest.main())
