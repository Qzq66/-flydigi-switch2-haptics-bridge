import copy,unittest
import test_multi_event_game_session as source_fixture
import test_phase_gap_integration as phase_fixture
from multi_game_policy_g58 import game_child_passed,build_game_plan,validate_game_plan
class Acceptance(unittest.TestCase):
    def fixture(self):
        _,c,_,_=source_fixture.Tests().run_source();p,_,_=phase_fixture.Integration().complete();stop=c['stopped_at_pc_clock']
        c.update(status='PASSED_SWITCH_FIDELITY_CHILD_PENDING_FLASH_LOG',terminal_received=True,terminal_ack_replied=True,collector_ended=True,timer_released=True,terminal_observed=True,host_flash_write=False,persistent_flydigi_commands=0,actual_switch_game=True,live_elapsed_seconds=120.,transport_diagnostics=p.snapshot(),input_relay=dict(last_pro_input='000000000880000880',reads_after_output_stop=10,nonneutral_reads_after_output_stop=1,last_nonneutral_at_pc_clock=stop+1,last_read_at_pc_clock=stop+6))
        return c
    def test_complete_synthetic_report_passes(self):self.assertTrue(game_child_passed(self.fixture()))
    def test_missing_third_event_fails(self):
        c=self.fixture();c['completed_events']=2;self.assertFalse(game_child_passed(c))
    def test_unconfirmed_stop_fails(self):
        c=self.fixture();c['output_stop_confirmed']=False;self.assertFalse(game_child_passed(c))
    def test_corrupt_report_hash_fails(self):
        c=self.fixture();c['successful_report_sha256']='wrong';self.assertFalse(game_child_passed(c))
    def test_output_fault_fails(self):
        c=self.fixture();c['output_fault']='injected';self.assertFalse(game_child_passed(c))
    def test_old_plan_rejected(self):
        plan=build_game_plan();plan['expected_flash_generation']=57
        with self.assertRaises(ValueError):validate_game_plan(plan)
if __name__=='__main__':unittest.main()
