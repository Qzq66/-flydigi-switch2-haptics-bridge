import ast,copy,pathlib,unittest
from startup_game_policy_g60 import build_game_plan,validate_game_plan,game_child_passed
from test_multi_game_acceptance import Acceptance
from fidelity_game_policy import can_click
ROOT=pathlib.Path(__file__).absolute().parents[1]
class Tests(unittest.TestCase):
    def fixture(self):
        c=Acceptance().fixture();c['startup_gate']=dict(version=1,quiet_seconds=.5,heartbeat_seconds=.080,automatic_arm=False,active_policy_unchanged=True);return c
    def test_new_metadata_required(self):
        c=self.fixture();self.assertTrue(game_child_passed(c));del c['startup_gate'];self.assertFalse(game_child_passed(c))
    def test_auto_arm_rejected(self):
        c=self.fixture();c['startup_gate']['automatic_arm']=True;self.assertFalse(game_child_passed(c))
    def test_old_output_fault_rejected(self):
        c=self.fixture();c['output_fault']='heartbeat';self.assertFalse(game_child_passed(c))
    def test_plan_current_generation_and_limits(self):
        p=build_game_plan();validate_game_plan(p);self.assertEqual(p['expected_flash_generation'],60);self.assertEqual(p['limits']['heartbeat_seconds'],.080);self.assertEqual(p['multi_event']['maximum_events'],3)
    def test_old_plan_rejected(self):
        p=build_game_plan();p['expected_flash_generation']=59
        with self.assertRaises(ValueError):validate_game_plan(p)
    def test_waiting_source_cannot_click(self):
        self.assertFalse(can_click(dict(clock='monotonic',phase='WAITING_SOURCE',source_neutral_ready=True,deadline_monotonic=120),1))
    def test_new_gui_has_no_forced_kill(self):
        t=ast.parse((ROOT/'tools/bridge_desktop_startup.py').read_text(encoding='utf-8'));self.assertFalse(any(isinstance(n,ast.Attribute) and n.attr in ('kill','terminate') for n in ast.walk(t)))
    def test_runner_keeps_bounded_host_and_cancel(self):
        text=(ROOT/'tools/run_startup_game_g60.py').read_text(encoding='utf-8');self.assertIn("plan['host_seconds']",text);self.assertIn("if cancelled():game.fail('Game cancelled')",text);self.assertIn("else 'WAITING_SOURCE'",text)
if __name__=='__main__':unittest.main()
