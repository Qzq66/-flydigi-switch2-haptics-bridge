"""Synthetic tests for the offline step-budget decomposition."""
import unittest
from step_budget_model import GATE, PERIOD, _stats, fault_decomposition, model


class Tests(unittest.TestCase):
    def rows(self):
        return [
            dict(start=10.000, tick_entry=10.0005, end=10.003, target=10.000),
            dict(start=10.010, tick_entry=10.0102, end=10.0103, target=10.008),
            dict(start=10.018707, tick_entry=10.018707, end=10.018707, target=10.016),
        ]

    def test_fault_arithmetic(self):
        result = fault_decomposition(self.rows())
        self.assertAlmostEqual(result['last_check_to_deadline'], .006, places=9)
        self.assertAlmostEqual(result['wake_delay'], .008707, places=9)
        self.assertAlmostEqual(result['wake_delay_allowance'], .006 + GATE, places=9)
        self.assertAlmostEqual(result['exceeded_allowance'], .008707 - .006 - GATE, places=9)
        self.assertAlmostEqual(result['observed_lateness'], .002707, places=9)

    def test_deadline_already_passed(self):
        rows = self.rows()
        rows[-1]['target'] = 10.008
        result = fault_decomposition(rows)
        self.assertAlmostEqual(result['last_check_to_deadline'], -.002, places=9)
        self.assertAlmostEqual(result['observed_lateness'], .010707, places=9)
        self.assertAlmostEqual(result['exceeded_allowance'], .008707 - (-.002) - GATE, places=9)

    def test_model_requires_matching_series(self):
        child = dict(output_lateness_seconds=[.001, .002], output_write_seconds=[.002],
                     dispatch_io=dict(first_fault=dict(context=self.rows())))
        with self.assertRaises(ValueError):
            model(child)

    def test_stats_are_ordered(self):
        values = _stats([.003, .001, .002])
        self.assertEqual(values['minimum'], .001)
        self.assertEqual(values['maximum'], .003)
        self.assertEqual(values['count'], 3)
        with self.assertRaises(ValueError):
            _stats([])

    def test_gate_and_period_unchanged(self):
        self.assertEqual(GATE, .004)
        self.assertEqual(PERIOD, .008)


if __name__ == '__main__':
    unittest.main()
