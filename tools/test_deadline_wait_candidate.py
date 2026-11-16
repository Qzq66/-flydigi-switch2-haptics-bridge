import math,types,unittest
from deadline_wait_candidate import request,WaitProxy
from sustained_game_session import SustainedGameSession
from sustained_validation import assess_sustained
from test_live_fidelity_candidate import frame,event,absolute,NEUTRAL

class Tests(unittest.TestCase):
    def replay(self,adaptive=False,external_preemption=False):
        now=[0.];sent=[];stops=[];seq=0
        s=SustainedGameSession(lambda:None,lambda l,r:sent.append((l,r)),lambda:(stops.append(True) or dict(runtime_disable_ack=True)),lambda:now[0],lambda n:now.__setitem__(0,now[0]+n))
        for i in range(101):
            now[0]=i*.005;s.feed(frame(now[0],[event(seq,round(now[0]*1e6),NEUTRAL)]));seq+=1
        s.arm(True,.5);schedule=[]
        for t in (5,15,25,35,45,55):schedule.extend([(.5+t,absolute()),(.5+t+.008,NEUTRAL)])
        index=0;injected=False;loops=0
        while not s.output.fault and s.output.stopped_at is None and loops<400000:
            events=[]
            while index<len(schedule) and schedule[index][0]<=now[0]:
                t,raw=schedule[index];events.append(event(seq,round(t*1e6),raw));seq+=1;index+=1
            s.feed(frame(now[0],events));s.tick();loops+=1
            if s.output.fault or s.output.stopped_at is not None:break
            remaining=s.target-now[0];delay=request(now[0],s.target,True) if adaptive else .001
            if not injected and s.output.frames>100 and 0<remaining<=.003 and (external_preemption or delay>0):
                now[0]+=.0087;injected=True
            else:now[0]+=delay+.0005 if delay else .0001
        return s.summary(),stops,loops,injected
    def test_no_wait_near_or_past_deadline(self):
        self.assertEqual(request(1.,1.002,True),0);self.assertEqual(request(1.,.99,True),0)
    def test_wait_never_exceeds_old_one_ms(self):
        for remain in (0,.001,.003,.0032,.004,.008):self.assertLessEqual(request(1.,1.+remain,True),.001)
    def test_prearm_and_muted_keep_old_wait(self):self.assertEqual(request(1.,None,False),.001)
    def test_invalid_clock_rejected(self):
        with self.assertRaises(ValueError):request(float('nan'),1.,True)
    def test_non_main_sleeps_unchanged(self):
        calls=[];base=types.SimpleNamespace(sleep=calls.append,perf_counter=lambda:0.);p=WaitProxy(base,lambda:None);p.sleep(.08);p.sleep(.01);self.assertEqual(calls,[.08,.01])
    def test_fixed_sleep_conditional_stall_triggers_existing_protection(self):
        c,stops,n,injected=self.replay();self.assertTrue(injected);self.assertIn('scheduler late',c['output_fault']);self.assertEqual(stops,[True])
    def test_deadline_policy_avoids_conditional_stall_and_preserves_pcm(self):
        c,stops,n,injected=self.replay(True);self.assertFalse(injected);a=assess_sustained(c);self.assertTrue(a['passed'],a);self.assertEqual(c['output_frames'],7500);self.assertEqual(stops,[True]);from test_sustained_session import Tests as Old;old=Old().complete();self.assertEqual(c['successful_pcm_sha256'],old['successful_pcm_sha256']);self.assertEqual(c['successful_report_sha256'],old['successful_report_sha256'])
    def test_unconditional_preemption_still_stops_no_catchup(self):
        c,stops,n,injected=self.replay(True,True);self.assertTrue(injected);self.assertIn('scheduler late',c['output_fault']);self.assertEqual(stops,[True]);self.assertLess(c['output_frames'],7500)
if __name__=='__main__':unittest.main()
