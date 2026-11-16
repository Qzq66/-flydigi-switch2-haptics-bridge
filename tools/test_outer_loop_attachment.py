import json,pathlib,tempfile,time,types,unittest
from outer_loop_probe import OuterLoopProbe,attach_to_private_core
import dispatch_windows_entry as windows
import test_dispatch_windows_entry as fixture
class Tests(unittest.TestCase):
    def test_private_install_does_not_patch_process_time(self):
        core=windows.load_core();old=core.time;system_sleep=time.sleep;game=core.GameSession;child=core.child
        restore=attach_to_private_core(core,OuterLoopProbe())
        try:self.assertIs(time.sleep,system_sleep);self.assertIsNot(core.time,old)
        finally:restore()
        self.assertIs(core.time,old);self.assertIs(core.GameSession,game);self.assertIs(core.child,child)
    def test_full_offline_windows_child_retains_acceptance_and_probe(self):
        helper=fixture.Tests();core,stops=helper.fake_core();core.time=time
        clock=[lambda:0.];original_factory=core.GameSession
        def factory(*a,**k):
            game=original_factory(*a,**k);clock[0]=game.clock;return game
        core.GameSession=factory;probe=OuterLoopProbe(clock=lambda:clock[0]());restore=attach_to_private_core(core,probe)
        try:
            with tempfile.TemporaryDirectory() as d:
                p=[pathlib.Path(d)/n for n in ('plan','backup','result','phase','arm')]
                code=windows.run_child(*p,core=core);report=json.loads(p[2].read_text())
            self.assertEqual(code,0);self.assertIn('outer_loop',report);self.assertGreater(report['outer_loop']['records'],0);self.assertEqual(stops,[1]);self.assertEqual(report['output_frames'],7500)
        finally:restore()
    def test_cancel_keeps_failure_and_stop_count(self):
        core,stops=fixture.Tests().fake_core('cancel');core.time=time;restore=attach_to_private_core(core,OuterLoopProbe())
        try:
            with tempfile.TemporaryDirectory() as d:
                p=[pathlib.Path(d)/n for n in ('plan','backup','result','phase','arm')];code=windows.run_child(*p,core=core);r=json.loads(p[2].read_text())
            self.assertEqual(code,1);self.assertEqual(r['status'],'INCOMPLETE');self.assertEqual(stops,[1])
        finally:restore()
    def test_clock_proxy_updates_underlying_game_clock(self):
        from outer_loop_probe import GameProxy
        old=lambda:0.;new=lambda:1.;game=types.SimpleNamespace(clock=old);wrapped=GameProxy(game,OuterLoopProbe());wrapped.clock=new;self.assertIs(game.clock,new)
if __name__=='__main__':unittest.main()
