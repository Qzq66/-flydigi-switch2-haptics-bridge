import contextlib,hashlib,io,json,os,pathlib,tempfile,types,unittest,sys
from unittest.mock import patch
import dispatch_windows_entry as entry
import dispatch_windows_profile as profile
from sustained_game_session import SustainedGameSession
from test_live_fidelity_candidate import frame,event,absolute,NEUTRAL
from bridge_input import NEUTRAL as INPUT_NEUTRAL
import test_phase_gap_integration as phase_fixture

class Tests(unittest.TestCase):
    def fake_core(self,scenario='complete'):
        now=[0.];stops=[];core=types.SimpleNamespace()
        core.GameSession=lambda en,se,st:SustainedGameSession(en,se,st,clock=lambda:now[0],pause=lambda n:now.__setitem__(0,now[0]+n))
        def stop():
            stops.append(1)
            if scenario=='stop_failure':raise OSError('injected unconfirmed stop')
            return dict(runtime_disable_ack=True)
        def child(plan,backup,result,phase,arm):
            game=core.GameSession(lambda:None,lambda l,r:None,stop);seq=0
            try:
                for i in range(101):
                    now[0]=i*.005;game.feed(frame(now[0],[event(seq,round(now[0]*1e6),NEUTRAL)]));seq+=1
                game.arm(True,.5);phase.write_text(json.dumps(dict(phase='ARMED',clock='monotonic')))
                if scenario in ('cancel','stop_failure'):game.fail('Game cancelled')
                else:
                    starts={5000,15000,25000,35000,45000,55000}
                    for offset in range(0,60009,8):
                        now[0]=game.target;events=[]
                        if offset in starts or offset-8 in starts:events=[event(seq,(500+offset)*1000,absolute() if offset in starts else NEUTRAL)];seq+=bool(events)
                        game.feed(frame(now[0],events));game.tick()
                        if game.output.stopped_at is not None:break
            except BaseException:pass
            finally:
                # Mirrors original core's single finally stop path.
                try:game.output.stop()
                except BaseException:pass
            c=game.summary();p,_,_=phase_fixture.Integration().complete();stopped=c.get('stopped_at_pc_clock') or now[0]
            c.update(status='PASSED_SWITCH_FIDELITY_CHILD_PENDING_FLASH_LOG',terminal_received=True,terminal_ack_replied=True,collector_ended=True,timer_released=True,terminal_observed=True,host_flash_write=False,persistent_flydigi_commands=0,actual_switch_game=True,live_elapsed_seconds=120.,transport_diagnostics=p.snapshot(),input_relay=dict(last_pro_input=INPUT_NEUTRAL.hex(),reads_after_output_stop=10,nonneutral_reads_after_output_stop=1,last_nonneutral_at_pc_clock=stopped+1,last_read_at_pc_clock=stopped+6))
            if scenario=='terminal_disconnect':c.update(terminal_received=False,terminal_observed=False)
            passed=profile.base_child_passed(c)
            if not passed:c['status']='INCOMPLETE'
            phase.write_text(json.dumps(dict(phase='ENDED',clock='monotonic')))
            result.write_text(json.dumps(c),encoding='utf-8');return 0 if passed else 1
        core.child=child;return core,stops
    def run_fake(self,scenario='complete',publisher_factory=entry.PhasePublisher,force_exit_failure=False):
        core,stops=self.fake_core(scenario)
        if force_exit_failure:
            original=core.child
            def failed_exit(*a):original(*a);return 1
            core.child=failed_exit
        with tempfile.TemporaryDirectory() as d:
            paths=[pathlib.Path(d)/n for n in ('plan','backup','result','phase','arm')]
            code=entry.run_child(*paths,core=core,publisher_factory=publisher_factory)
            report=json.loads(paths[2].read_text());phase=json.loads(paths[3].read_text()) if paths[3].exists() else None
        return code,report,phase,stops
    def test_complete_fake_windows_child_drains_ended_and_passes(self):
        code,c,phase,stops=self.run_fake();self.assertEqual(code,0);self.assertTrue(profile.child_passed(c));self.assertEqual(phase['phase'],'ENDED');self.assertEqual(stops,[1]);self.assertTrue(c['phase_publisher']['closed'])
    def test_cancel_preserves_failure_and_stops_once(self):
        code,c,phase,stops=self.run_fake('cancel');self.assertEqual(code,1);self.assertEqual(c['status'],'INCOMPLETE');self.assertIn('cancelled',c['output_fault']);self.assertEqual(stops,[1])
    def test_unconfirmed_stop_not_retried_by_adapter(self):
        code,c,phase,stops=self.run_fake('stop_failure');self.assertEqual(code,1);self.assertIn('original child output stop unconfirmed',c['adapter_cleanup_errors']);self.assertEqual(len(stops),2) # fail() then original finally; no third adapter attempt
    def test_writer_close_failure_cannot_become_success(self):
        class FailedPublisher:
            def __init__(self,writer):pass
            def publish(self,*a,**k):pass
            def check(self):pass
            def close(self,*a):raise TimeoutError('injected close timeout')
            def summary(self):return dict(closed=False,error=None,pending_count=1)
        code,c,phase,stops=self.run_fake(publisher_factory=FailedPublisher);self.assertEqual(code,1);self.assertIn('publisher: TimeoutError',c['adapter_cleanup_errors']);self.assertEqual(stops,[1])
    def test_play_requires_extra_authorization_before_core_load(self):
        with patch.object(sys,'argv',['entry','--play','dummy']),patch.object(entry,'load_core') as load,contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):entry.main()
            load.assert_not_called()
    def test_internal_child_without_parent_authorization_refused(self):
        with patch.object(sys,'argv',['entry','--child','a','b','c','d','e']),patch.dict(os.environ,{entry.AUTH_KEY:''}),patch.object(entry,'run_child') as run,contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):entry.main()
            run.assert_not_called()
    def test_profile_keeps_all_original_limits(self):
        old=profile.base_plan();new=profile.build_game_plan();self.assertEqual(old['limits'],new['limits']);self.assertEqual(old['multi_event'],new['multi_event']);self.assertEqual(old['receive_budget_seconds'],new['receive_budget_seconds']);profile.validate_game_plan(new)
    def test_core_load_preserves_frozen_source(self):
        p=entry.ROOT/'tools/run_sustained_game_g61.py';before=hashlib.sha256(p.read_bytes()).hexdigest();core=entry.load_core();self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),before);self.assertEqual(core.__file__,str(pathlib.Path(entry.__file__).absolute()))
    def test_terminal_disconnect_not_accepted(self):
        code,c,phase,stops=self.run_fake('terminal_disconnect');self.assertEqual(code,1);self.assertFalse(c['terminal_observed']);self.assertEqual(stops,[1])
    def test_failed_child_exit_never_upgraded(self):
        code,c,phase,stops=self.run_fake(force_exit_failure=True);self.assertEqual(code,1);self.assertEqual(c['status'],'INCOMPLETE')
    def test_prepare_never_loads_hardware_core(self):
        with tempfile.TemporaryDirectory() as d:
            out=pathlib.Path(d)/'plan.json'
            with patch.object(sys,'argv',['entry','--prepare',str(out)]),patch.object(entry,'load_core') as load,contextlib.redirect_stdout(io.StringIO()):self.assertEqual(entry.main(),0);load.assert_not_called()
            self.assertTrue(json.loads(out.read_text())['requires_separate_additional_trial_authorization'])
    def test_parent_rejects_writer_that_did_not_close(self):
        with patch.object(profile,'base_parent_passed',return_value=True),patch.object(profile,'base_child_passed',return_value=True):
            self.assertFalse(profile.parent_passed(dict(child=dict(phase_publisher=dict(closed=False,error=None,pending_count=0))),{}))
    def test_authorization_environment_restored_after_error(self):
        def fail(*a):
            self.assertEqual(os.environ.get(entry.AUTH_KEY),'explicit');raise RuntimeError('injected parent failure')
        with patch.dict(os.environ,{entry.AUTH_KEY:'prior'}),patch.object(sys,'argv',['entry','--play','p','--picotool','pic','--authorize-additional-trial']),patch.object(entry,'load_core',return_value=types.SimpleNamespace(play=fail)):
            with self.assertRaises(RuntimeError):entry.main()
            self.assertEqual(os.environ[entry.AUTH_KEY],'prior')
    def test_missing_dispatch_observation_not_accepted(self):
        code,c,phase,stops=self.run_fake();self.assertEqual(code,0);del c['dispatch_io'];self.assertFalse(profile.child_passed(c))
if __name__=='__main__':unittest.main()
