import unittest,hashlib
from bounded_multi_event_session import MultiEventSession,BridgeFault
class Tests(unittest.TestCase):
    def make(self,send=None,ack=True):
        self.now=0.;self.calls=[]
        def stop():self.calls.append('stop');return dict(runtime_disable_ack=ack)
        s=MultiEventSession(lambda:self.calls.append('enable'),send or (lambda l,r:self.calls.append('send')),stop,lambda:self.now,lambda n:setattr(self,'now',self.now+n))
        s.renderer.upstream=True;s.renderer.last_received=0.;s.arm();return s
    def block(self,s,active):
        self.now=s.renderer.output_start if s.renderer.rendered_until is None else s.renderer.rendered_until
        s.renderer.last_received=self.now;s.renderer.values=[[.02 if active else 0.,160.,0.,320.] for _ in range(2)];return s.tick(self.now)
    def episode(self,s):
        self.block(s,True)
        for _ in range(65):self.block(s,False)
    def test_three_events_stop_once_after_neutral(self):
        s=self.make()
        for _ in range(3):self.episode(s)
        self.assertEqual(self.calls.count('enable'),1);self.assertEqual(self.calls.count('stop'),1)
        self.assertIsNone(self.block(s,False));s.stop();self.assertEqual(self.calls.count('stop'),1)
        x=s.summary();self.assertEqual(x['completed_events'],3);self.assertEqual(x['active_ms'],[24,24]);self.assertTrue(x['output_stop_confirmed'])
    def test_send_failure_latches_and_stops(self):
        def bad(*a):raise OSError('injected')
        s=self.make(send=bad);self.block(s,True);self.assertTrue(s.fault);self.assertEqual(s.submitted,0);self.assertEqual(self.calls.count('stop'),1);self.block(s,False);self.assertEqual(self.calls.count('stop'),1)
    def test_late_dispatch_stops(self):
        s=self.make();self.now=s.renderer.output_start+.005;s.tick(s.renderer.output_start);self.assertTrue(s.fault);self.assertEqual(self.calls.count('stop'),1)
    def test_heartbeat_stops(self):
        s=self.make();self.now=.1;s.tick(.1);self.assertTrue(s.fault)
    def test_success_hashes_only_after_writer_return(self):
        frames=[];s=self.make(send=lambda l,r:frames.append((bytes(l),bytes(r))));self.block(s,True);x=s.summary();self.assertEqual(x['successful_pcm_sha256'][0],hashlib.sha256(frames[0][0]).hexdigest());self.assertEqual(x['successful_submission_frames'],1)
    def test_unconfirmed_stop_not_passed(self):
        s=self.make(ack=False)
        with self.assertRaises(BridgeFault):s.stop()
        self.assertFalse(s.summary()['output_stop_confirmed']);self.assertTrue(s.cleanup_error)
    def test_oversized_sample_rejected_before_writer(self):
        s=self.make()
        with self.assertRaises(BridgeFault):s.tracked_send([138]*8,[128]*8)
        self.assertEqual(s.submitted,0)

    def test_three_wire_decoded_events_through_session(self):
        from test_live_fidelity_candidate import frame,event,absolute,NEUTRAL
        s=self.make();s.feed(frame(0.,flags=7));outputs=[]
        s.external_send=lambda l,r:outputs.append((list(l),list(r)))
        for seq,source_ms in enumerate(range(0,2000,8)):
            self.now=.064+source_ms/1000
            active=source_ms in (0,608,1216)
            s.feed(frame(self.now,[event(seq,source_ms*1000,absolute() if active else NEUTRAL)]))
            s.tick(self.now)
            if s.stopped_at is not None:break
        self.assertIsNone(s.fault);self.assertEqual(s.renderer.completed_events,3);self.assertEqual(self.calls.count('enable'),1);self.assertEqual(self.calls.count('stop'),1)
        self.assertEqual(s.summary()['active_ms'],[24,24]);self.assertTrue(outputs);self.assertEqual(outputs[-1],([128]*8,[128]*8));self.assertEqual(s.submitted,len(outputs))

if __name__=='__main__':unittest.main()

