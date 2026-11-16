import copy,math,unittest
from startup_ready_game_session import StartupReadyGameSession
from test_live_fidelity_candidate import frame,event,absolute,NEUTRAL
from multi_event_validation import assess_multi
from fidelity_network_session import StreamSession

class Tests(unittest.TestCase):
    def setUp(self):
        self.now=0.;self.calls=[]
        self.s=StartupReadyGameSession(lambda:self.calls.append('enable'),lambda l,r:self.calls.append('send'),lambda:(self.calls.append('stop') or dict(runtime_disable_ack=True)),lambda:self.now,lambda n:setattr(self,'now',self.now+n))
        self.seq=0
    def feed(self,t,flags=7,raw=NEUTRAL):
        self.now=t;self.s.feed(frame(t,[event(self.seq,round(t*1e6),raw)],flags=flags));self.seq+=1
    def qualify(self,start=0.):
        for i in range(101):self.feed(start+i*.005);self.s.tick()
    def test_unconfigured_gap_is_silent_not_fault(self):
        self.feed(0,3);self.now=.081;self.s.tick()
        self.assertIsNone(self.s.output.fault);self.assertFalse(self.s.source_ready());self.assertEqual(self.calls,[])
    def test_configured_startup_gap_is_not_active_fault(self):
        self.feed(0);self.now=.1;self.s.tick();self.assertIsNone(self.s.output.fault);self.assertEqual(self.calls,[])
    def test_recovery_requires_new_quiet_window(self):
        self.qualify();self.assertTrue(self.s.source_ready());self.now=.59;self.s.tick();self.assertFalse(self.s.source_ready())
        self.feed(.6);self.assertFalse(self.s.source_ready());self.qualify(.61);self.assertTrue(self.s.source_ready());self.assertEqual(self.calls,[])
    def test_gap_detected_even_without_intermediate_tick(self):
        self.qualify();self.feed(.7);self.assertFalse(self.s.source_ready());self.assertEqual(self.s.startup_gap_count,1)
    def test_unconfigured_never_ready(self):
        for i in range(121):self.feed(i*.005,3)
        self.assertFalse(self.s.source_ready())
    def test_no_automatic_enable(self):
        self.qualify();self.assertTrue(self.s.source_ready());self.assertEqual(self.calls,[]);self.assertFalse(self.s.output.renderer.armed)
    def test_premature_manual_arm_rejected_without_enable(self):
        self.feed(0)
        with self.assertRaises(Exception):self.s.arm(True,0)
        self.assertTrue(self.s.output.fault);self.assertEqual(self.calls,[])
    def test_controls_non_neutral_rejected(self):
        self.qualify()
        with self.assertRaises(Exception):self.s.arm(False,.5)
        self.assertEqual(self.calls,[])
    def test_late_arm_rejected(self):
        self.qualify()
        with self.assertRaises(Exception):self.s.arm(True,101)
        self.assertEqual(self.calls,[])
    def test_sequence_gap_still_faults(self):
        self.feed(0);self.seq=9;self.feed(.01);self.assertTrue(self.s.output.fault)
    def test_source_clock_reversal_still_faults(self):
        self.feed(.1);self.feed(.09);self.assertTrue(self.s.output.fault)
    def test_nan_tick_faults(self):
        self.feed(0);self.now=float('nan');self.s.tick();self.assertTrue(self.s.output.fault)
    def test_cancel_remains_latched(self):
        self.qualify();self.s.fail('cancelled');self.feed(.51);self.assertFalse(self.s.source_ready());self.assertEqual(self.calls,[])
    def test_active_heartbeat_stop_unchanged(self):
        self.qualify();target=self.s.arm(True,.5);self.now=.581;StreamSession.tick(self.s.output,target)
        self.assertIn('wire heartbeat timeout',self.s.output.fault);self.assertEqual(self.calls,['enable','stop']);self.assertFalse(self.s.output.dirty)
    def test_fault_does_not_rearm(self):
        self.qualify();self.s.arm(True,.5);self.now=.581;self.s.tick();self.feed(.59)
        with self.assertRaises(Exception):self.s.arm(True,.59)
        self.assertEqual(self.calls,['enable','stop'])
    def test_complete_three_events_independent_hashes(self):
        self.qualify();self.s.arm(True,.5)
        for offset in range(0,2000,8):
            self.now=self.s.target
            self.s.feed(frame(self.now,[event(self.seq,(500+offset)*1000,absolute() if offset in (0,608,1216) else NEUTRAL)]));self.seq+=1
            self.s.tick()
            if self.s.output.stopped_at is not None:break
        c=self.s.summary();a=assess_multi(c);self.assertTrue(a['passed'],a);self.assertEqual(c['completed_events'],3);self.assertEqual(self.calls.count('stop'),1)

if __name__=='__main__':unittest.main()
