"""Synthetic tests for priority_coverage_probe (no timing, no device)."""
import unittest

import priority_coverage_probe as probe


class Tests(unittest.TestCase):
    def test_gate_verdict_is_the_product_rule(self):
        self.assertEqual(probe.gate_verdict(0.0), 'OK')
        self.assertEqual(probe.gate_verdict(0.003999), 'OK')
        self.assertEqual(probe.gate_verdict(0.004), 'FAULT')
        self.assertEqual(probe.gate_verdict(0.0046), 'FAULT')

    def test_summarize_dispatch_counts_thresholds(self):
        summary = probe.summarize_dispatch([0.001, 0.0029, 0.0035, 0.004, 0.007])
        self.assertEqual(summary['dispatched'], 5)
        self.assertEqual(summary['at_or_over_4ms'], 2)
        self.assertEqual(summary['over_3ms'], 3)
        self.assertEqual(summary['over_6ms'], 1)
        self.assertEqual(summary['lateness_seconds']['maximum'], 0.007)

    def test_summarize_wakes_counts_thresholds(self):
        summary = probe.summarize_wakes([0.0005, 0.0015, 0.0045, 0.0075])
        self.assertEqual(summary['over_1ms'], 3)
        self.assertEqual(summary['over_3ms'], 2)
        self.assertEqual(summary['over_4ms'], 2)
        self.assertEqual(summary['over_6ms'], 1)

    def test_stats_reports_count_and_bounds(self):
        self.assertEqual(probe.stats([]), dict(count=0))
        summary = probe.stats([3.0, 1.0, 2.0])
        self.assertEqual(summary['count'], 3)
        self.assertEqual(summary['minimum'], 1.0)
        self.assertEqual(summary['maximum'], 3.0)
        self.assertEqual(summary['median'], 2.0)

    def test_validate_arm_rejects_unknown(self):
        for arm in probe.ARMS:
            self.assertEqual(probe.validate_arm(arm), arm)
        with self.assertRaises(ValueError):
            probe.validate_arm('boost_everything')

    def test_constants_are_unchanged(self):
        self.assertEqual(probe.PERIOD, 0.008)
        self.assertEqual(probe.GATE, 0.004)
        self.assertEqual(probe.WAIT, 0.001)


if __name__ == '__main__':
    unittest.main()
