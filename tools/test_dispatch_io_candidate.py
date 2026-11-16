import copy,json,threading,unittest
import test_sustained_session as source_fixture
from sustained_validation import assess_sustained
from dispatch_io_candidate import CandidateLoop
from test_live_fidelity_candidate import frame,event,absolute,NEUTRAL
class Tests(unittest.TestCase):
    def setup(self,writer=lambda p:None):
        f=source_fixture.Tests();f.now=0.;f.sent=[];f.stops=[];f.seq=0
        from sustained_game_session import SustainedGameSession
        f.s=SustainedGameSession(lambda:None,lambda l,r:f.sent.append((l,r)),lambda:(f.stops.append(True) or dict(runtime_disable_ack=True)),lambda:f.now,lambda n:setattr(f,'now',f.now+n))
        loop=CandidateLoop(f.s,writer)
        for i in range(101):
            f.now=i*.005;loop.step([frame(f.now,[event(f.seq,round(f.now*1e6),NEUTRAL)])]);f.seq+=1
        f.s.arm(True,.5);return f,loop
    def test_blocked_ui_writer_keeps_full_sixty_second_pcm_equivalence(self):
        entered=threading.Event();release=threading.Event()
        def writer(p):entered.set();release.wait(2)
        f,loop=self.setup(writer);starts={5000,15000,25000,35000,45000,55000}
        try:
            loop.publisher.publish('ARMED');self.assertTrue(entered.wait(1))
            for offset in range(0,60009,8):
                f.now=f.s.target;events=[]
                if offset in starts or offset-8 in starts:events=[event(f.seq,(500+offset)*1000,absolute() if offset in starts else NEUTRAL)];f.seq+=bool(events)
                loop.step([frame(f.now,events)],phase='ARMED',fields=dict(completed_events=f.s.output.renderer.completed_events))
                if f.s.output.stopped_at is not None:break
            c=f.s.summary();result=assess_sustained(c);self.assertTrue(result['passed'],result);old=source_fixture.Tests().complete();self.assertEqual(c['successful_report_sha256'],old['successful_report_sha256']);self.assertEqual(c['successful_pcm_sha256'],old['successful_pcm_sha256']);self.assertEqual(c['squared_code_sum'],old['squared_code_sum']);self.assertEqual(c['event_records'],old['event_records']);self.assertEqual(c['output_frames'],7500);self.assertEqual(f.stops,[True]);self.assertLessEqual(len(loop.summary()['recent']),32)
        finally:release.set();loop.close()
    def test_exact_tick_clock_captured_before_slow_stop(self):
        f,loop=self.setup();f.now=f.s.target+.005
        def slow_stop():
            f.stops.append(True);f.now+=.080;return dict(runtime_disable_ack=True)
        f.s.output.stop_output=slow_stop
        try:
            loop.step([frame(f.now)]);r=loop.first_fault;self.assertAlmostEqual(r['lateness_seconds'],.005);self.assertEqual(r['frames_after'],0);self.assertTrue(r['stop_confirmed']);self.assertEqual(f.stops,[True]);self.assertGreater(loop.recent[-1]['end']-r['tick_entry'],.079)
        finally:loop.close()
    def test_writer_failure_stops_output_no_retry(self):
        called=threading.Event()
        def writer(p):called.set();raise OSError('disk failure')
        f,loop=self.setup(writer);loop.publisher.publish('ARMED');self.assertTrue(called.wait(1));loop.publisher.thread.join(1)
        with self.assertRaises(RuntimeError):loop.step()
        self.assertEqual(f.stops,[True]);self.assertTrue(f.s.output.fault);self.assertIsNone(loop.first_fault['tick_entry']);self.assertFalse(loop.first_fault['observed_before_stop_clock_value'])
        with self.assertRaises(RuntimeError):loop.close()
    def test_input_sequence_gap_still_faults_before_render(self):
        f,loop=self.setup();f.now=f.s.target
        try:loop.step([frame(f.now,[event(99999,round(f.now*1e6),NEUTRAL)])]);self.assertTrue(f.s.output.fault);self.assertEqual(len(f.sent),0)
        finally:loop.close()
    def test_source_exception_stops_before_any_frame(self):
        f,loop=self.setup()
        with self.assertRaises(OSError):loop.step([OSError('collector failure')])
        self.assertEqual(len(f.sent),0);self.assertEqual(f.stops,[True]);loop.close()
    def test_no_hot_attach(self):
        f,loop=self.setup()
        try:
            with self.assertRaises(ValueError):CandidateLoop(f.s,lambda p:None)
        finally:loop.close()
    def test_old_and_candidate_emit_same_first_frame(self):
        original=source_fixture.Tests();original.setup_session();original.now=original.s.target;original.s.feed(frame(original.now));original.s.tick()
        f,loop=self.setup();f.now=f.s.target
        try:loop.step([frame(f.now)]);self.assertEqual(f.sent,original.sent);self.assertEqual(f.s.output.frames,1)
        finally:loop.close();original.s.output.stop()
    def test_close_stops_once_and_rejects_further_steps(self):
        f,loop=self.setup();loop.close();loop.close();self.assertEqual(f.stops,[True])
        with self.assertRaises(RuntimeError):loop.step()
if __name__=='__main__':unittest.main()
