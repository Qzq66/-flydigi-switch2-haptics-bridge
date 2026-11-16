import unittest
from poll_timing_probe_v2 import RetainedTimingClient
from test_poll_timing_probe import Clock,Client

class Retention(unittest.TestCase):
    def test_worst_gap_and_timeout_survive_hundreds_of_lower_priority_incidents(self):
        clock=Clock();raw=Client(clock);client=RetainedTimingClient(raw,clock=clock)
        client.poll();raw.sock.sock.timeout=True;client.poll();raw.sock.sock.timeout=False
        clock.now+=.05;client.poll();worst=client.snapshot()['worst_response_gap_context']
        self.assertGreater(worst['event']['response_gap'],.080)
        for _ in range(200):clock.now+=.03;client.poll()
        snapshot=client.snapshot()
        self.assertEqual(snapshot['worst_response_gap_context'],worst)
        self.assertTrue(any(e['event']['outcome']=='timeout' for e in snapshot['critical_events']))
        self.assertTrue(any(e['outcome']=='timeout' for e in snapshot['worst_response_gap_context']['before']))
        self.assertFalse(any(e['outcome']=='timeout' for e in snapshot['detailed_recent']))

    def test_new_larger_gap_replaces_worst_and_snapshot_is_independent(self):
        clock=Clock();client=RetainedTimingClient(Client(clock),clock=clock);client.poll();clock.now+=.1;client.poll()
        snapshot=client.snapshot();first=snapshot['worst_response_gap_context']['event']['response_gap']
        clock.now+=.2;client.poll()
        self.assertGreater(client.snapshot()['worst_response_gap_context']['event']['response_gap'],first)
        self.assertEqual(snapshot['worst_response_gap_context']['event']['response_gap'],first)

    def test_critical_retention_is_bounded(self):
        clock=Clock();raw=Client(clock);client=RetainedTimingClient(raw,clock=clock)
        raw.sock.sock.timeout=True
        for _ in range(100):client.poll()
        self.assertEqual(len(client.snapshot()['critical_events']),32)

if __name__=='__main__':unittest.main()
