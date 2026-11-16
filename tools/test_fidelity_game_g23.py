import copy,unittest
from fidelity_game_policy_g23 import ROOT,build_game_plan,validate_game_plan,GameSession,game_parent_passed
from test_fidelity_game import Game as PreviousGame
from test_live_fidelity_candidate import frame,event,absolute

class G23(unittest.TestCase):
    def test_plan_explicitly_binds_generation23_and_retains_limits(self):
        p=build_game_plan();validate_game_plan(p)
        self.assertEqual(p['expected_flash_generation'],23)
        self.assertFalse(p['heartbeat_gap_accepted_as_realtime'])
        self.assertEqual(p['limits']['heartbeat_seconds'],.080)
        self.assertEqual(p['limits']['maximum_output_lateness_seconds'],.004)
        for key,value in (('expected_flash_generation',22),('heartbeat_gap_accepted_as_realtime',True)):
            with self.assertRaises(ValueError):validate_game_plan(dict(p,**{key:value}))

    def test_fault_after_episode_never_replays_but_archive_and_terminal_continue(self):
        fixture=PreviousGame();g,clock,calls=fixture.complete();frames=g.output.frames
        clock.now+=.081;g.tick();self.assertIsNotNone(g.output.fault)
        self.assertTrue(g.output.summary()['output_stop_confirmed'])
        count=len(g.events)
        for n in range(300):
            clock.pause(.05);g.feed(frame(clock(),[event(count+n,round(clock()*1e6),absolute())]));g.tick()
        g.feed(frame(clock(),flags=25))
        self.assertEqual(g.output.frames,frames);self.assertTrue(g.terminal)
        self.assertEqual(len(g.events),count+300)

    def test_new_parent_binding_rejects_previous_physical_generation(self):
        fixture=PreviousGame();fixture.plan=build_game_plan();p=fixture.parent_report()
        p['firmware_preflight']['baseline_generation']=23
        self.assertTrue(game_parent_passed(p,fixture.plan))
        p['firmware_preflight']['baseline_generation']=22
        self.assertFalse(game_parent_passed(p,fixture.plan))

if __name__=='__main__':unittest.main()
