import unittest
from wake_timing_probe import SleepProbe,WakeObservedClient
from test_poll_timing_probe import Clock,Client

class WakeTiming(unittest.TestCase):
    def test_measures_existing_request_without_changing_it(self):
        clock=Clock();calls=[]
        def pause(seconds):calls.append(seconds);clock.now+=.015625
        probe=SleepProbe(clock,pause);probe(.004);s=probe.snapshot()
        self.assertEqual(calls,[.004]);self.assertAlmostEqual(s['worst']['overshoot_seconds'],.011625)
        self.assertEqual(s['overshoot_bucket_counts'],[0,0,0,1,0])

    def test_worst_sleep_is_not_lost_and_snapshots_are_independent(self):
        clock=Clock();delay=[.02]
        probe=SleepProbe(clock,lambda n:setattr(clock,'now',clock.now+delay[0]))
        probe(.004);snapshot=probe.snapshot();delay[0]=.004
        for _ in range(100):probe(.004)
        s=probe.snapshot();self.assertEqual(s['worst'],snapshot['worst']);self.assertEqual(snapshot['count'],1)
        self.assertEqual(len(s['recent']),64);self.assertEqual(sum(s['overshoot_bucket_counts']),101)

    def test_worst_reply_gap_keeps_its_actual_collector_sleep(self):
        clock=Clock();delay=[.015]
        probe=SleepProbe(clock,lambda n:setattr(clock,'now',clock.now+delay[0]))
        client=WakeObservedClient(Client(clock),sleep_probe=probe,clock=clock)
        client.poll();probe(.004);client.poll();first=client.snapshot()['worst_response_gap_context']
        self.assertAlmostEqual(first['event']['collector_sleep_before_poll']['actual_seconds'],.015)
        delay[0]=.004
        for _ in range(100):probe(.004);client.poll()
        self.assertEqual(client.snapshot()['worst_response_gap_context'],first)

    def test_invalid_request_or_clock_does_not_create_false_sample(self):
        clock=Clock();probe=SleepProbe(clock,lambda n:setattr(clock,'now',clock.now-1))
        with self.assertRaises(ValueError):probe(.004)
        self.assertEqual(probe.count,0)
        with self.assertRaises(ValueError):probe(float('nan'))

    def test_context_includes_only_preceding_sleep_not_later_sleep(self):
        clock=Clock();probe=SleepProbe(clock,lambda n:setattr(clock,'now',clock.now+n))
        client=WakeObservedClient(Client(clock),sleep_probe=probe,clock=clock);client.poll()
        probe(.004);client.poll();snapshot=client.snapshot();event=snapshot['worst_response_gap_context']['event']
        sleep=event['collector_sleep_before_poll'];self.assertLessEqual(sleep['end'],event['start'])
        probe(.1);self.assertEqual(client.snapshot()['worst_response_gap_context']['event'],event)

    def test_immediate_ack_retry_does_not_reuse_an_old_sleep(self):
        clock=Clock();probe=SleepProbe(clock,lambda n:setattr(clock,'now',clock.now+n))
        client=WakeObservedClient(Client(clock),sleep_probe=probe,clock=clock)
        client.poll();probe(.004);client.poll();client.poll()
        self.assertIsNone(client.snapshot()['detailed_recent'][-1]['collector_sleep_before_poll'])

if __name__=='__main__':unittest.main()
