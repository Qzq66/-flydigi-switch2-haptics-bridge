import ast,unittest
from passive_reply_policy_g30 import ROOT,build_plan,validate_plan

class ReplyPlan(unittest.TestCase):
    def test_plan_uses30_and_keeps_diagnostic_only_packet_rules(self):
        p=build_plan();validate_plan(p);self.assertEqual(p['expected_flash_generation'],30)
        self.assertFalse(p['adopt_into_game_output']);self.assertFalse(p['observer_changes_packet_acceptance'])
        self.assertFalse(p['board_telemetry_over_udp']);self.assertEqual(p['receive_budget_seconds'],.012)
        self.assertEqual(p['request_history_limit'],512)
        with self.assertRaises(ValueError):validate_plan(dict(p,adopt_into_game_output=True))

    def test_entry_has_no_actuator_and_does_not_replace_transport(self):
        source=(ROOT/'tools/run_passive_reply_g30.py').read_text(encoding='utf-8');tree=ast.parse(source)
        calls={n.func.attr for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)}
        self.assertFalse(calls.intersection({'mode','stream','waveform','stop','arm'}))
        self.assertIn('from short_wait_transport import ShortWaitClient as Client',source)
        self.assertIn('client=ProvenanceClient',source)
        self.assertNotIn('GameSession',source)

if __name__=='__main__':unittest.main()
