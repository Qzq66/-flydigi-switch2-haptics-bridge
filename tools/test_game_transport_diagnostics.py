import unittest
from game_transport_diagnostics import ObservedClient

class Clock:
    def __init__(self):self.now=0.
    def __call__(self):return self.now

class Client:
    def __init__(self,clock):self.clock=clock;self.terminal_ack_replied=False;self.n=0
    def poll(self,final_ack=False):
        self.n+=1;self.clock.now+=.06 if self.n==2 else .003
        if self.n==2:return None
        self.terminal_ack_replied=final_ack
        return dict(received_at=self.clock(),boot=7,source_us=self.n*4000,
            flags=25 if final_ack else 7,events=[],rtt_ms=3.)

class TransportDiagnostics(unittest.TestCase):
    def test_preserves_frames_and_observes_timeout_gap(self):
        clock=Clock();raw=Client(clock);client=ObservedClient(raw,clock)
        first=client.poll();self.assertEqual(first['boot'],7)
        self.assertIsNone(client.poll());client.poll();s=client.snapshot()
        self.assertEqual((s['poll_calls'],s['responses'],s['timeouts']),(3,2,1))
        self.assertAlmostEqual(s['maximum_response_gap_seconds'],.063)
        self.assertEqual(s['observed_boot_ids'],[7])

    def test_end_confirmation_uses_bounded_retries(self):
        clock=Clock();raw=Client(clock);client=ObservedClient(raw,clock)
        self.assertEqual(client.confirm_end()['flags'],25)
        self.assertTrue(client.terminal_ack_replied);self.assertEqual(raw.n,1)

    def test_snapshot_fault_context_is_not_mutated_by_later_polling(self):
        clock=Clock();client=ObservedClient(Client(clock),clock);client.poll();frozen=client.snapshot()
        for _ in range(100):client.poll()
        self.assertEqual(len(frozen['recent']),1);self.assertEqual(frozen['responses'],1)
        self.assertEqual(len(client.snapshot()['recent']),64)

    def test_restart_error_is_recorded_and_propagated_without_retry(self):
        class Restart(Client):
            def poll(self,*args,**kwargs):raise RuntimeError('Pico restarted; explicit new session required')
        clock=Clock();client=ObservedClient(Restart(clock),clock)
        with self.assertRaisesRegex(RuntimeError,'restarted'):client.poll()
        self.assertEqual(client.calls,1);self.assertEqual(client.snapshot()['recent'][-1]['kind'],'error')

if __name__=='__main__':unittest.main()
