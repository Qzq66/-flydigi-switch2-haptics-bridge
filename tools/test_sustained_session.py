import copy,unittest
from sustained_game_session import SustainedGameSession
from sustained_validation import assess_sustained
from test_live_fidelity_candidate import frame,event,absolute,NEUTRAL
class Tests(unittest.TestCase):
    def setup_session(self):
        self.now=0.;self.sent=[];self.stops=[];self.seq=0
        self.s=SustainedGameSession(lambda:None,lambda l,r:self.sent.append((l,r)),lambda:(self.stops.append(True) or dict(runtime_disable_ack=True)),lambda:self.now,lambda n:setattr(self,'now',self.now+n))
        for i in range(101):
            self.now=i*.005;self.s.feed(frame(self.now,[event(self.seq,round(self.now*1e6),NEUTRAL)]));self.seq+=1
        self.s.arm(True,.5)
    def complete(self):
        self.setup_session();starts={5000,15000,25000,35000,45000,55000}
        for offset in range(0,60009,8):
            self.now=self.s.target;batch=[]
            if offset in starts or offset-8 in starts:
                batch=[event(self.seq,(500+offset)*1000,absolute() if offset in starts else NEUTRAL)];self.seq+=1
            self.s.feed(frame(self.now,batch));self.s.tick()
            if self.s.output.stopped_at is not None:break
        return self.s.summary()
    def test_complete_sixty_seconds_and_six_hashes(self):
        c=self.complete();a=assess_sustained(c);self.assertTrue(a['passed'],a);self.assertEqual(len(self.sent),7500);self.assertEqual(self.stops,[True]);self.assertEqual(c['completed_events'],6);self.assertGreaterEqual(c['stopped_at_pc_clock']-c['armed_at_pc_clock'],60)
    def test_cannot_pass_as_old_three_event(self):
        c=self.complete();c['completed_events']=3;self.assertFalse(assess_sustained(c)['passed'])
    def test_short_window_rejected(self):
        c=self.complete();c['output_frames']=1900;self.assertFalse(assess_sustained(c)['passed'])
    def test_digest_mutation_rejected(self):
        c=self.complete();c['successful_report_sha256']='bad';self.assertFalse(assess_sustained(c)['passed'])
    def test_active_heartbeat_failure_stops(self):
        self.setup_session();self.now=.7;self.s.tick();self.assertTrue(self.s.output.fault);self.assertEqual(self.stops,[True])
    def test_writer_frame_cap(self):
        self.setup_session();self.s.output.submitted=7500
        with self.assertRaises(Exception):self.s.output.tracked_send([128]*8,[128]*8)
    def test_writer_dose_cap(self):
        self.setup_session();self.s.output.submitted_dose=[48000,48000]
        with self.assertRaises(Exception):self.s.output.tracked_send([137]*8,[137]*8)
    def test_event_not_distributed_rejected(self):
        c=self.complete();c['event_records'][-1]['quiet_completed_at']=c['event_records'][0]['quiet_completed_at']+10;self.assertFalse(assess_sustained(c)['passed'])
if __name__=='__main__':unittest.main()
