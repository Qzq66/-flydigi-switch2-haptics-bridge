"""Synthetic tests for recv_spin_probe (no socket, no device)."""
import unittest

import recv_spin_probe as probe


class Tests(unittest.TestCase):
    def test_summarize_receive_counts_sequence_gaps(self):
        summary = probe.summarize_receive([1, 2, 4], [0.000, 0.010, 0.030], sent=3)
        self.assertEqual(summary['sent'], 3)
        self.assertEqual(summary['received'], 3)
        self.assertEqual(summary['lost'], 0)
        self.assertEqual(summary['sequence_gaps'], 1)
        self.assertEqual(summary['gaps_over_8ms'], 2)
        self.assertEqual(summary['gaps_over_16ms'], 1)

    def test_summarize_receive_reports_loss(self):
        summary = probe.summarize_receive([1, 2], [0.000, 0.008], sent=5)
        self.assertEqual(summary['received'], 2)
        self.assertEqual(summary['lost'], 3)

    def test_arms(self):
        for arm in probe.ARMS:
            self.assertEqual(probe.validate_arm(arm), arm)
        with self.assertRaises(ValueError):
            probe.validate_arm('spin_9ms')

    def test_constants_unchanged(self):
        self.assertEqual(probe.PERIOD, 0.008)
        self.assertEqual(probe.GATE, 0.004)
        self.assertEqual(probe.PACKET_INTERVAL, 0.008)


if __name__ == '__main__':
    unittest.main()
