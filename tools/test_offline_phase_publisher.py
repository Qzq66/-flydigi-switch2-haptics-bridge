import json,threading,unittest
from offline_phase_publisher import PhasePublisher
class Tests(unittest.TestCase):
    def test_blocked_writer_does_not_block_caller_and_only_latest_pending(self):
        entered=threading.Event();release=threading.Event();writes=[]
        def writer(p):entered.set();release.wait(2);writes.append(json.loads(p))
        s=PhasePublisher(writer)
        try:
            s.publish('ARMED',completed_events=0);self.assertTrue(entered.wait(1))
            for i in range(100):s.publish('ARMED',completed_events=i)
            s.publish('MUTED');self.assertEqual(s.summary()['pending_count'],1);self.assertGreater(s.summary()['coalesced'],0)
        finally:release.set();s.close()
        self.assertEqual(len(writes),2);self.assertEqual(writes[-1]['phase'],'MUTED')
    def test_error_latched_no_retry(self):
        attempted=threading.Event();calls=[]
        def writer(p):calls.append(p);attempted.set();raise OSError('injected disk failure')
        s=PhasePublisher(writer);s.publish('ARMED');self.assertTrue(attempted.wait(1));s.thread.join(1)
        with self.assertRaises(RuntimeError):s.check()
        with self.assertRaises(RuntimeError):s.publish('ARMED')
        with self.assertRaises(RuntimeError):s.close()
        self.assertEqual(len(calls),1)
    def test_close_timeout_does_not_force_kill(self):
        entered=threading.Event();release=threading.Event()
        def writer(p):entered.set();release.wait(2)
        s=PhasePublisher(writer);s.publish('ARMED');self.assertTrue(entered.wait(1))
        try:
            with self.assertRaises(TimeoutError):s.close(.01)
        finally:release.set();s.close(1)
    def test_close_drains_final_state(self):
        writes=[];s=PhasePublisher(writes.append);s.publish('ENDED');s.close();self.assertEqual(json.loads(writes[-1])['phase'],'ENDED')
    def test_invalid_phase_and_nonfinite_rejected(self):
        s=PhasePublisher(lambda p:None)
        try:
            with self.assertRaises(ValueError):s.publish('UNKNOWN')
            with self.assertRaises(ValueError):s.publish('ARMED',left=float('nan'))
            with self.assertRaises(ValueError):s.publish('ARMED',items=[])
            with self.assertRaises(ValueError):s.publish('ARMED',text='x'*3000)
        finally:s.close()
    def test_publish_after_close_rejected(self):
        s=PhasePublisher(lambda p:None);s.close()
        with self.assertRaises(RuntimeError):s.publish('ENDED')
if __name__=='__main__':unittest.main()
