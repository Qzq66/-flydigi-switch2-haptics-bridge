"""Offline regressions: incomplete or failed game output never passes supervision."""
import copy,pathlib,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).absolute().parents[1]/'handoff/2026-10-22/work'))
from bridge_process import game_end_check_succeeded

class Gate(unittest.TestCase):
    def setUp(self):
        self.good=dict(status='PASSED_SWITCH_WIFI_GAME_PILOT_PROGRAM_CHECKS',ended_reason='terminal stream complete',terminal_received=True,terminal_ack_replied=True,collector_ended=True,timer_released=True,runtime_disable_ack=True,motor_output_enabled=True,output_frames=100,maximum_offset=12,prompt_counts=[1,1],active_samples=[120,120])
    def test_valid_and_one_sided(self):
        self.assertTrue(game_end_check_succeeded(self.good,0))
        self.good.update(prompt_counts=[1,0],active_samples=[120,0]);self.assertTrue(game_end_check_succeeded(self.good,0))
    def test_fail_closed(self):
        changes=dict(status='INCOMPLETE',ended_reason='wire heartbeat timeout',terminal_received=False,terminal_ack_replied=False,collector_ended=False,timer_released=False,runtime_disable_ack=False,motor_output_enabled=False,output_frames=0,maximum_offset=13,prompt_counts=[4,1],active_samples=[119,120],cleanup_error='failed stop',error='fault',pico_reset_error='failed reset',output_fault='calibrated prompt count cap')
        for key,value in changes.items():
            with self.subTest(key=key):
                bad=copy.deepcopy(self.good);bad[key]=value;self.assertFalse(game_end_check_succeeded(bad,0))
        self.assertFalse(game_end_check_succeeded(self.good,1))
        self.assertFalse(game_end_check_succeeded(None,0))
    def test_neutral_only_not_output_success(self):
        self.good.update(prompt_counts=[0,0],active_samples=[0,0],maximum_offset=0)
        self.assertFalse(game_end_check_succeeded(self.good,0))
    def test_staged_requires_explicit_arm_and_silent_preparation(self):
        self.good['staged_game']=True;self.assertFalse(game_end_check_succeeded(self.good,0))
        self.good.update(pre_arm_output_frames=0,pre_arm_prompt_counts=[0,0],armed_at_pc_clock=10.0)
        self.assertTrue(game_end_check_succeeded(self.good,0))
        for key,value in (('pre_arm_output_frames',1),('pre_arm_prompt_counts',[1,0]),('armed_at_pc_clock',None)):
            bad=copy.deepcopy(self.good);bad[key]=value;self.assertFalse(game_end_check_succeeded(bad,0))

if __name__=='__main__':unittest.main()
