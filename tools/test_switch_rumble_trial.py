import unittest
from switch_rumble_trial import run
from switch_rumble_packet import NEUTRAL


class Clock:
    def __init__(self): self.now = 0.
    def read(self): return self.now
    def sleep(self, delta): self.now += max(0., delta)


class TrialTests(unittest.TestCase):
    def setup_trial(self, delay=.0005, fail_at=None):
        clock, packets = Clock(), []
        def send(p):
            packets.append(p)
            clock.now += delay
            if len(packets) == fail_at: raise OSError('injected failure')
        return clock, packets, send

    def test_one_pulse_then_neutral(self):
        clock, packets, send = self.setup_trial()
        r = run(send, clock=clock.read, sleep=clock.sleep)
        self.assertEqual(r['status'], 'PULSE_SENT')
        self.assertEqual(r['active_frames'], 30)
        self.assertEqual(len(packets), 32)
        self.assertEqual(packets[0][2:10], NEUTRAL*2)
        self.assertEqual(packets[-1][2:10], NEUTRAL*2)
        self.assertTrue(r['stop_write_completed'])

    def test_slow_neutral_never_enables(self):
        clock, packets, send = self.setup_trial(delay=.006)
        r = run(send, clock=clock.read, sleep=clock.sleep)
        self.assertEqual(r['status'], 'STOPPED_ON_FAULT')
        self.assertEqual(len(packets), 1)
        self.assertEqual(packets[0][2:10], NEUTRAL*2)

    def test_failed_active_attempt_gets_one_cleanup(self):
        clock, packets, send = self.setup_trial(fail_at=2)
        r = run(send, clock=clock.read, sleep=clock.sleep)
        self.assertEqual(len(packets), 3)
        self.assertEqual(packets[-1][2:10], NEUTRAL*2)
        self.assertEqual(r['active_frames'], 0)

    def test_cancel_prevents_activation(self):
        clock, packets, send = self.setup_trial()
        r = run(send, cancelled=lambda: True, clock=clock.read, sleep=clock.sleep)
        self.assertEqual(len(packets), 1)
        self.assertEqual(r['active_frames'], 0)

    def test_late_dispatch_stops_without_catchup(self):
        clock, packets, send = self.setup_trial()
        def sleep(delta): clock.now += delta + .010
        r = run(send, clock=clock.read, sleep=sleep)
        self.assertEqual(r['error'], 'DISPATCH_EXCEEDED_4MS')
        self.assertEqual(r['active_frames'], 1)
        self.assertEqual(packets[-1][2:10], NEUTRAL*2)

    def test_cleanup_failure_is_explicit(self):
        clock, packets, send = self.setup_trial(fail_at=32)
        r = run(send, clock=clock.read, sleep=clock.sleep)
        self.assertEqual(r['status'], 'STOP_WRITE_FAILED')
        self.assertFalse(r['stop_write_completed'])


if __name__ == '__main__': unittest.main()
