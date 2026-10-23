import copy,unittest
from test_v043_host_acceptance import evidence
from v043_game_gate import validate,assess
from bridge_game_phase import can_arm,remaining

def accepted():
    p,c,b=evidence();p['firmware_preflight']['firmware_sha256']='ab'*32
    a=assess(p,c,b,True);f=dict(verified=True,variant='v043',firmware_sha256='ab'*32,baseline_generation=11)
    return p,c,b,a,f

class Gate(unittest.TestCase):
    def test_same_image_requires_complete_recomputed_acceptance(self):
        result=validate(*accepted());self.assertTrue(result['verified']);self.assertTrue(result['staged_click_required'])
        self.assertEqual((result['prompt_ms'],result['maximum_offset'],result['maximum_prompts_per_side'],result['wire_timeout_ms']),(120,12,3,80))
    def test_wrong_image_or_old_flash_baseline_rejected(self):
        for changes in (dict(firmware_sha256='cd'*32),dict(variant='v042'),dict(verified=False),dict(baseline_generation=10)):
            args=list(accepted());args[4].update(changes)
            with self.subTest(changes=changes),self.assertRaises(ValueError):validate(*args)
    def test_saved_pass_label_cannot_hide_bad_input_or_configuration(self):
        for change in ('late','configuration','capture'):
            p,c,b,a,f=accepted()
            if change=='late':p['child']['input_relay']['last_nonneutral_at_pc_clock']=1073
            elif change=='configuration':p['configuration_unchanged']=False
            else:c['complete']=False
            with self.subTest(change=change),self.assertRaises(ValueError):validate(p,c,b,a,f)
    def test_later_verified_generation_can_reuse_same_image_acceptance(self):
        p,c,b,a,f=accepted();f['baseline_generation']=13;self.assertTrue(validate(p,c,b,a,f)['verified'])

class UIClock(unittest.TestCase):
    def test_shared_clock_deadline_and_child_margin(self):
        status=dict(phase='INPUT_READY',clock='monotonic',deadline_monotonic=118)
        self.assertTrue(can_arm(status,112));self.assertFalse(can_arm(status,113));self.assertEqual(remaining(status,119),0)
    def test_old_or_invalid_clock_never_arms(self):
        for status in (dict(phase='INPUT_READY',deadline=100000),dict(phase='INPUT_READY',clock='monotonic',deadline_monotonic=float('nan'))):
            self.assertFalse(can_arm(status,0))
    def test_repeated_or_ended_phase_cannot_arm(self):
        for phase in ('ARMED','ENDED'):
            self.assertFalse(can_arm(dict(phase=phase,clock='monotonic',deadline_monotonic=118),20))

if __name__=='__main__':unittest.main()
