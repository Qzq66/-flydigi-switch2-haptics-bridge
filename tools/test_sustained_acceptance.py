import ast,json,pathlib,types,copy,unittest
from unittest.mock import patch
from sustained_game_policy_g61 import build_game_plan,validate_game_plan,game_child_passed
from test_sustained_session import Tests as SessionFixture
from test_phase_gap_integration import Integration
import sustained_config_owner as gate
ROOT=pathlib.Path(__file__).absolute().parents[1]
class Tests(unittest.TestCase):
    def fixture(self):
        c=SessionFixture().complete();p,_,_=Integration().complete();stop=c['stopped_at_pc_clock'];c.update(status='PASSED_SWITCH_FIDELITY_CHILD_PENDING_FLASH_LOG',terminal_received=True,terminal_ack_replied=True,collector_ended=True,timer_released=True,terminal_observed=True,host_flash_write=False,persistent_flydigi_commands=0,actual_switch_game=True,live_elapsed_seconds=120.,transport_diagnostics=p.snapshot(),input_relay=dict(last_pro_input='000000000880000880',reads_after_output_stop=10,nonneutral_reads_after_output_stop=1,last_nonneutral_at_pc_clock=stop+1,last_read_at_pc_clock=stop+6));return c
    def test_complete_new_budget_acceptance(self):self.assertTrue(game_child_passed(self.fixture()))
    def test_input_not_released_rejected(self):
        c=self.fixture();c['input_relay']['last_pro_input']='bad';self.assertFalse(game_child_passed(c))
    def test_failure_is_not_hidden(self):
        c=self.fixture();c['output_fault']='late';self.assertFalse(game_child_passed(c))
    def test_plan_explicit_budgets_and_binding(self):
        p=build_game_plan();validate_game_plan(p);self.assertEqual(p['expected_flash_generation'],61);self.assertEqual(p['multi_event']['output_seconds'],60);self.assertEqual(p['arm_latest_seconds'],50);self.assertEqual(p['limits']['heartbeat_seconds'],.08)
    def test_old_generation_rejected(self):
        p=build_game_plan();p['expected_flash_generation']=60
        with self.assertRaises(ValueError):validate_game_plan(p)
    def test_owner_requires_exact_normal_config(self):
        private=ROOT/'handoff/2026-10-22/work/private';sel=json.loads((private/'startup-config-selection-2026-11-15.json').read_text());old=json.loads(pathlib.Path(sel['current_configuration_backup']).read_text());n=json.loads((private/'config-read-control-raw-20261115-154118.json').read_text())['samples'][0];expected=dict(identity_sha256=old['identity_sha256'],state=n['state_before'],ram=n['ram']);current=copy.deepcopy(expected)
        owner=types.SimpleNamespace(safe=types.SimpleNamespace(digest=lambda v:current['identity_sha256'],read_ram=lambda r,i:(bytes.fromhex(current['ram'][{1:'global',4:'mapping',5:'lighting',6:'motors'}[i]]['raw_hex']),{})),identity=lambda *a:None)
        reader=types.SimpleNamespace(ask=lambda *a,**k:b'',state=lambda:current['state'])
        import tempfile
        with patch('bridge_windows.load_owner',return_value=owner):o=gate.load_owner()
        with tempfile.TemporaryDirectory() as d:
            o.backup(reader,pathlib.Path(d)/'a.json');raw=bytearray.fromhex(current['ram']['motors']['raw_hex']);raw[56]^=64;current['ram']['motors']['raw_hex']=raw.hex()
            with self.assertRaises(ValueError):o.backup(reader,pathlib.Path(d)/'b.json')
if __name__=='__main__':unittest.main()
