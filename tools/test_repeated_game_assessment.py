"""Synthetic repeated-event evidence plus unchanged archived single-event evidence."""
import json,unittest
from test_v043_game_assessment import fixture
from assess_v043_staged_game import assess,ROOT
from game_scenarios import scene_can_arm
from v043_game_gate import authorize

def repeated_fixture():
    p,c,b,proof=fixture();child=p['child'];anchor=child['source_clock_anchor']
    arm=anchor['source_us']+(child['armed_at_pc_clock']-anchor['pc_clock'])*1e6
    neutral='0001404000014040';active='801860b2801860b2'
    # This encoded pulse returns to neutral in its second 5ms group.
    wire=[dict(at_us=round(arm+offset),sequence=i,motors=word,flags=7) for i,(offset,word) in enumerate(((-1000000,neutral),(1000000,active),(1100000,neutral),(6005000,active),(6200000,neutral)))]
    child.update(events=wire,prompt_counts=[2,2],active_samples=[240,240]);p['scene']='dodge-attack-repeat'
    c['events']=[dict(at_us=e['at_us'],motors_hex=e['motors']) for e in wire]
    return p,c,b,proof

def evaluate(args):return assess(*args,True,True,True,scene='dodge-attack-repeat')

class RepeatedAssessment(unittest.TestCase):
    def test_two_complete_separated_events_pass(self):
        r=evaluate(repeated_fixture())
        self.assertTrue(all(r['checks'].values()),r['checks'])
        self.assertEqual(r['source_episodes']['quiet_gaps_us'],[[5000000],[5000000]])

    def test_wrong_counts_or_partial_outputs_fail(self):
        for counts,samples in (([1,1],[120,120]),([3,3],[360,360]),([2,1],[240,120]),([2,2],[239,240])):
            args=repeated_fixture();args[0]['child'].update(prompt_counts=counts,active_samples=samples)
            self.assertEqual(evaluate(args)['status'],'INCOMPLETE')

    def test_short_gap_fails_even_if_counts_claim_two(self):
        args=repeated_fixture()
        for event in args[0]['child']['events'][3:]:event['at_us']-=1
        self.assertFalse(evaluate(args)['checks']['five_seconds_source_quiet_between'])

    def test_no_neutral_or_disabled_source_does_not_count_as_second_episode(self):
        for disabled in (False,True):
            args=repeated_fixture();wire=args[0]['child']['events']
            if disabled:
                for event in wire[3:]:event['flags']=3
            else:wire[2]['motors']=wire[1]['motors']
            self.assertFalse(evaluate(args)['checks']['two_source_episodes_each'])

    def test_old_scene_or_late_arm_cannot_pass(self):
        args=repeated_fixture();args[0]['scene']='dodge-attack'
        self.assertFalse(evaluate(args)['checks']['scene_recorded'])
        args=repeated_fixture();child=args[0]['child'];child['live_started_at_pc_clock']=child['armed_at_pc_clock']-98
        self.assertFalse(evaluate(args)['checks']['repeat_arm_reserve'])

    def test_ui_reserve_is_conservative_and_old_scenes_unchanged(self):
        state=dict(phase='INPUT_READY',clock='monotonic',deadline_monotonic=100)
        self.assertTrue(scene_can_arm('dodge-attack-repeat',state,79.999))
        self.assertFalse(scene_can_arm('dodge-attack-repeat',state,80))
        for scene in ('door','dodge-attack'):
            self.assertTrue(scene_can_arm(scene,state,94.999))
            self.assertFalse(scene_can_arm(scene,state,95))
        self.assertFalse(scene_can_arm('dodge-attack-repeat',dict(state,phase='ARMED'),0))
        self.assertFalse(scene_can_arm('dodge-attack-repeat',dict(state,clock='perf_counter'),0))

    def test_archived_single_event_assessments_remain_identical(self):
        load=lambda name:json.loads((ROOT/'docs'/name).read_text(encoding='utf-8-sig'))
        for stamp,cap,base,scene,prefix in (
            ('20261023-234407','20261023-235027','20261023-224226','door','V043_STAGED_GAME_ASSESSMENT_'),
            ('20261023-235855','20261024-000336','20261023-235027','door','V043_STAGED_GAME_ASSESSMENT_'),
            ('20261024-131624','20261024-132206','20261024-131454','dodge-attack','V043_DODGE_ATTACK_ASSESSMENT_'),
            ('20261024-132744','20261024-133155','20261024-132206','dodge-attack','V043_DODGE_ATTACK_ASSESSMENT_')):
            with self.subTest(stamp=stamp):
                program=load('WINDOWS_V043_GAME_RECHECK_'+stamp+'.json')
                proof=authorize(ROOT/'docs/V043_STAGED_GAME_PREREQUISITE_20261023.json',program['firmware_preflight'])
                result=assess(program,load('V043_HOST_CAPTURE_'+cap+'.json')['newest'],load('V043_HOST_CAPTURE_'+base+'.json')['newest'],proof,True,True,True,scene=scene)
                self.assertEqual(result,load(prefix+stamp+'.json'))

if __name__=='__main__':unittest.main()
