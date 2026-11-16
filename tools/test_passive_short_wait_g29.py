import ast,unittest
from passive_short_wait_policy_g29 import ROOT,build_plan,validate_plan

class ShortPlan(unittest.TestCase):
    def test_plan_binds29_and_explicit_receive_budget_without_relaxing_limits(self):
        p=build_plan();validate_plan(p);self.assertEqual(p['expected_flash_generation'],29)
        self.assertEqual(p['receive_budget_seconds'],.012);self.assertEqual(p['reference_receive_budget_seconds'],.060)
        self.assertEqual(p['heartbeat_observation_seconds'],.080);self.assertEqual(p['motor_commands'],0)
        self.assertFalse(p['wire_protocol_changed']);self.assertFalse(p['receive_deadline_is_hard_realtime_guarantee'])
        with self.assertRaises(ValueError):validate_plan(dict(p,receive_budget_seconds=.060))

    def test_entry_has_no_actuator_and_uses_separate_transport(self):
        source=(ROOT/'tools/run_passive_short_wait_g29.py').read_text(encoding='utf-8');tree=ast.parse(source)
        calls={n.func.attr for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)}
        self.assertFalse(calls.intersection({'mode','stream','waveform','stop','arm'}))
        self.assertIn('from short_wait_transport import ShortWaitClient as Client',source)
        self.assertNotIn('GameSession',source);self.assertNotIn('StreamSession',source)

if __name__=='__main__':unittest.main()
