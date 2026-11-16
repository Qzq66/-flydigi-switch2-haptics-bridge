"""Synthetic tests for spin_wait_probe (no timing, no device)."""
import unittest

import spin_wait_probe as probe


class Tests(unittest.TestCase):
    def test_margin_table(self):
        self.assertIsNone(probe.margin_for('baseline'))
        self.assertEqual(probe.margin_for('spin_1ms'), 0.001)
        self.assertEqual(probe.margin_for('spin_2ms'), 0.002)
        self.assertEqual(probe.margin_for('spin_3ms'), 0.003)
        self.assertEqual(probe.margin_for('spin_2ms_boost'), 0.002)

    def test_unknown_arm_rejected(self):
        with self.assertRaises(ValueError):
            probe.margin_for('spin_9ms')

    def test_summarize_lateness_counts_gate(self):
        summary = probe.summarize_lateness([0.001, 0.0039, 0.004, 0.006])
        self.assertEqual(summary['dispatched'], 4)
        self.assertEqual(summary['at_or_over_4ms'], 2)
        self.assertEqual(summary['over_3ms'], 3)
        self.assertEqual(summary['over_2ms'], 3)

    def test_boost_arm_is_declared(self):
        self.assertIn('spin_2ms_boost', probe.MARGINS)
        self.assertEqual(probe.BOOST_ARMS, ('spin_2ms_boost',))

    def test_constants_unchanged(self):
        self.assertEqual(probe.PERIOD, 0.008)
        self.assertEqual(probe.GATE, 0.004)


if __name__ == '__main__':
    unittest.main()
