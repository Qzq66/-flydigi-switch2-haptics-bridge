import ast,unittest
from passive_timing_policy_g26 import ROOT,build_plan,validate_plan

class TimingPlan(unittest.TestCase):
    def test_plan_explicitly_requires_generation26_and_zero_output(self):
        plan=build_plan();validate_plan(plan)
        self.assertEqual(plan['expected_flash_generation'],26);self.assertEqual(plan['motor_commands'],0)
        self.assertEqual(plan['input_forwarding'],'read_xinput_then_send_fixed_neutral')
        self.assertEqual(plan['heartbeat_observation_seconds'],.080)
        with self.assertRaises(ValueError):validate_plan(dict(plan,expected_flash_generation=25))

    def test_entry_contains_no_actuator_or_renderer(self):
        source=(ROOT/'tools/run_passive_timing_g26.py').read_text(encoding='utf-8');tree=ast.parse(source)
        calls={n.func.attr for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)}
        self.assertFalse(calls.intersection({'mode','stream','waveform','stop','arm'}))
        self.assertNotIn('GameSession',source);self.assertNotIn('StreamSession',source)

if __name__=='__main__':unittest.main()
