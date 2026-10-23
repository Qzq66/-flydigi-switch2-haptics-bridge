"""Synthetic extended metadata over the old real waveform corpus, never new hardware evidence."""
import copy,json,unittest
from assess_v043_staged_game import assess,ROOT,NEUTRAL

def fixture():
    load=lambda name:json.loads((ROOT/'docs'/name).read_text(encoding='utf-8'))
    p=load('WINDOWS_V042_GAME_RECHECK_20261023-162326.json');c=load('WINDOWS_V042_GAME_CAPTURE_20261023-162326.json')['newest']
    proof=dict(verified=True,firmware_sha256='ab'*32)
    p.update(status='PASSED_V043_SWITCH_GAME_PROGRAM_CHECKS',input_acceptance_gate=proof,firmware_preflight=dict(firmware_sha256='ab'*32,baseline_generation=13))
    start=p['child']['armed_at_pc_clock']-15;p['child'].update(live_started_at_pc_clock=start,live_elapsed_seconds=119.9)
    p['child']['input_relay'].update(last_pro_input=NEUTRAL.hex(),last_read_at_pc_clock=start+119.8)
    c.update(generation=14,elapsed_ms=132000)
    return p,c,dict(generation=13),proof

class GameAssessment(unittest.TestCase):
    def test_complete_single_door_evidence(self):
        result=assess(*fixture(),True,True,True)
        self.assertTrue(all(result['checks'].values()),result['checks']);self.assertEqual(result['status'],'PASSED_V043_120S_STAGED_GAME_LIMITED_NOTIFICATION')
    def test_incomplete_pulse_prearm_output_and_excess_offset_rejected(self):
        for changes in (dict(pre_arm_output_frames=1),dict(active_samples=[112,120]),dict(maximum_offset=13),dict(output_fault='wire heartbeat timeout')):
            args=list(fixture());args[0]['child'].update(changes)
            with self.subTest(changes=changes):self.assertEqual(assess(*args,True,True,True)['status'],'INCOMPLETE')
    def test_early_end_stale_or_mismatched_capture_rejected(self):
        for changes in (dict(reason='capacity_limit'),dict(generation=13),dict(complete=False),dict(stream_end='drain_timeout'),dict(events=[])):
            args=list(fixture());args[1].update(changes)
            with self.subTest(changes=changes):self.assertEqual(assess(*args,True,True,True)['status'],'INCOMPLETE')
    def test_human_evidence_is_required(self):
        for flags in ((False,True,True),(True,False,True),(True,True,False)):
            with self.subTest(flags=flags):self.assertEqual(assess(*fixture(),*flags)['status'],'INCOMPLETE')
    def test_journal_clock_epoch_does_not_shift_network_arm_correlation(self):
        args=list(fixture());expected=assess(*args,True,True,True)
        for event in args[1]['events']:event['at_us']=max(0,event['at_us']-500000)
        result=assess(*args,True,True,True)
        self.assertEqual(result['decoded_post_arm_active_groups'],expected['decoded_post_arm_active_groups'])
        self.assertEqual(result['first_active_ms_after_arm'],expected['first_active_ms_after_arm'])
        self.assertEqual(result['status'],expected['status'])

if __name__=='__main__':unittest.main()
