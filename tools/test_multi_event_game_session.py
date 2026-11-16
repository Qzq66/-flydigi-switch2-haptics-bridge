import copy,unittest
from multi_event_game_session import MultiGameSession
from multi_event_validation import assess_multi
from test_live_fidelity_candidate import frame,event,absolute,NEUTRAL
class Tests(unittest.TestCase):
    def run_source(self):
        self.now=0.;sent=[];stops=[]
        s=MultiGameSession(lambda:None,lambda l,r:sent.append((l,r)),lambda:(stops.append(True) or dict(runtime_disable_ack=True)),lambda:self.now,lambda n:setattr(self,'now',self.now+n))
        s.feed(frame(0.,[event(0,0,NEUTRAL)]));self.now=.6;s.feed(frame(.6,[event(1,599000,NEUTRAL)]));s.arm(True,.6)
        for seq,offset in enumerate(range(0,2000,8),2):
            source=600+offset;self.now=s.target
            s.feed(frame(self.now,[event(seq,source*1000,absolute() if offset in (0,608,1216) else NEUTRAL)]));s.tick()
            if s.output.stopped_at is not None:break
        return s,s.summary(),sent,stops
    def test_game_gate_source_to_independent_hashes(self):
        s,c,frames,stops=self.run_source();a=assess_multi(c);self.assertTrue(a['passed'],a);self.assertEqual(len(stops),1);self.assertEqual(len(frames),c['output_frames']);self.assertEqual(c['active_ms'],[24,24])
    def test_corrupt_hash_rejected(self):
        s,c,f,x=self.run_source();c['successful_report_sha256']='wrong';self.assertFalse(assess_multi(c)['passed'])
    def test_missing_event_record_rejected(self):
        s,c,f,x=self.run_source();c['event_records'].pop();self.assertFalse(assess_multi(c)['passed'])
    def test_cancel_is_idempotent_and_stops(self):
        s,c,f,x=self.run_source();s.fail('cancelled');s.output.stop();self.assertEqual(len(x),1);self.assertTrue(s.output.fault)
if __name__=='__main__':unittest.main()

