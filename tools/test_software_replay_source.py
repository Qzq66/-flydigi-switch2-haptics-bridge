import unittest
from software_replay_source import schedule, ACTIVE, NEUTRAL
from sustained_game_session import SustainedGameSession
from sustained_validation import assess_sustained
from test_live_fidelity_candidate import frame, event

class Tests(unittest.TestCase):
    def test_default_and_heavier_profile_change_only_duration(self):
        old=schedule(.5,0);heavy=schedule(.5,0,280)
        self.assertEqual(len(old),12)
        self.assertEqual(old[::2],heavy[::2])
        for i in range(0,12,2):
            self.assertEqual(old[i][1],ACTIVE)
            self.assertEqual(old[i+1][1],heavy[i+1][1])
            self.assertEqual(heavy[i+1][1],NEUTRAL)
            self.assertEqual(old[i+1][0]-old[i][0],8000)
            self.assertEqual(heavy[i+1][0]-heavy[i][0],280000)

    def test_other_profiles_rejected(self):
        for value in (0,9,320,1000):
            with self.subTest(value=value),self.assertRaises(ValueError):schedule(0,0,value)

    def complete(self,duration):
        now=[0.];stops=[]
        s=SustainedGameSession(lambda:None,lambda l,r:None,
            lambda:(stops.append(True) or dict(runtime_disable_ack=True)),
            clock=lambda:now[0],pause=lambda n:now.__setitem__(0,now[0]+n))
        seq=0
        for i in range(101):
            now[0]=i*.005;s.feed(frame(now[0],[event(seq,round(now[0]*1e6),NEUTRAL)]));seq+=1
        s.arm(True,.5);rows=schedule(s.output.renderer.armed_at,0,duration);index=0
        for _ in range(7502):
            now[0]=s.target;batch=[]
            while index<len(rows) and rows[index][0]<=round(now[0]*1e6):
                at,raw=rows[index];batch.append(event(seq,at,raw));seq+=1;index+=1
            s.feed(frame(now[0],batch));s.tick()
            if s.output.stopped_at is not None:break
        result=s.summary()
        self.assertTrue(assess_sustained(result)['passed'],result.get('output_fault'))
        self.assertEqual(stops,[True])
        return result

    def test_default_full_window_preserves_small_duty(self):
        result=self.complete(8)
        self.assertEqual(result['active_ms'],[48,48])

    def test_280ms_profile_fits_unchanged_event_and_session_budgets(self):
        result=self.complete(280)
        self.assertEqual(result['active_ms'],[1680,1680])
        self.assertEqual(result['output_frames'],7500)
        self.assertEqual(result['completed_events'],6)
        for row in result['event_records']:
            self.assertEqual(row['active_ms'],[280,280])
            self.assertTrue(all(n<=8000 for n in row['squared_code_sum']))

if __name__=='__main__':unittest.main()
