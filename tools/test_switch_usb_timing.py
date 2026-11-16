import unittest
import switch_usb_timing as t
import switch_rumble_packet as packet


class Tests(unittest.TestCase):
    def test_fast_frame_is_clean(self):
        out = t.evaluate(due=1.000, now=1.001, io_elapsed=0.0005)
        self.assertAlmostEqual(out['late_ms'], 1.0)
        self.assertAlmostEqual(out['io_ms'], 0.5)
        self.assertFalse(out['slow_io'])

    def test_slow_transport_is_recorded_not_fatal(self):
        # 6 ms completion: over the dispatch period, under the transport bound.
        out = t.evaluate(due=1.000, now=1.0002, io_elapsed=0.006)
        self.assertTrue(out['slow_io'])
        self.assertAlmostEqual(out['io_ms'], 6.0)

    def test_transport_timeout_stops(self):
        with self.assertRaisesRegex(t.TimingFault, 'TRANSPORT_TIMEOUT'):
            t.evaluate(due=1.0, now=1.0001, io_elapsed=0.060)

    def test_dispatch_late_still_stops(self):
        with self.assertRaisesRegex(t.TimingFault, 'DISPATCH_LATE'):
            t.evaluate(due=1.0, now=1.005, io_elapsed=0.0001)

    def test_invalid_inputs_rejected(self):
        for kwargs in (dict(due=1.0, now=0.9, io_elapsed=-0.1),
                       dict(due='x', now=1.0, io_elapsed=0.0),
                       dict(due=1.0, now=1.0, io_elapsed=0.0, transport_timeout=0)):
            with self.assertRaises(ValueError):
                t.evaluate(**kwargs)

    def test_stats_keep_transport_and_dispatch_apart(self):
        stats = t.Stats()
        for late, io in ((0.5, 0.3), (1.2, 5.5), (0.9, 6.5)):
            stats.add(late, io)
        summary = stats.summary()
        self.assertEqual(summary['count'], 3)
        self.assertEqual(summary['io_over_4ms'], 2)
        self.assertEqual(summary['dispatch_over_4ms'], 0)
        self.assertAlmostEqual(summary['transport']['max_ms'], 6.5)

    def test_neutral_plan_is_monotonic(self):
        frames = t.neutral_frames(4)
        self.assertEqual([i for i, _ in frames], [0, 1, 2, 3])
        self.assertAlmostEqual(frames[3][1], 0.012)

    def test_classify_records_late_dispatch_without_stopping(self):
        outcome = t.classify(due=1.0, now=1.006, io_elapsed=0.002)
        self.assertAlmostEqual(outcome['late_ms'], 6.0)
        self.assertTrue(outcome['over_dispatch_budget'])

    def test_classify_still_stops_on_transport_timeout(self):
        with self.assertRaisesRegex(t.TimingFault, 'TRANSPORT_TIMEOUT'):
            t.classify(due=1.0, now=1.0001, io_elapsed=0.060)

    def test_random_transport_does_not_abort_simulation(self):
        # 24 neutral frames at the 4 ms grid, each completion takes 6 ms.
        stats = t.Stats()
        for index, due in t.neutral_frames(24):
            outcome = t.evaluate(due=due, now=due + 0.0002, io_elapsed=0.006)
            stats.add(outcome['late_ms'], outcome['io_ms'])
        summary = stats.summary()
        self.assertEqual(summary['count'], 24)
        self.assertEqual(summary['io_over_4ms'], 24)


class NeutralPacketTests(unittest.TestCase):
    def test_every_sequence_is_neutral_on_both_sides(self):
        for sequence in range(16):
            data = packet.report(sequence)
            self.assertEqual(data[2:6], packet.NEUTRAL)
            self.assertEqual(data[6:10], packet.NEUTRAL)
            self.assertEqual(len(data), 64)


if __name__ == '__main__':
    unittest.main()
