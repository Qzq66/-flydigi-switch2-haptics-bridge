"""Offline tests for outer_gap_audit; synthetic rows only, no timing or hardware."""
import pathlib, sys, unittest
sys.path.insert(0, str(pathlib.Path(__file__).absolute().parent))
from outer_gap_audit import audit, GATE


def row(step, start, drain=2e-6, enqueue=3e-7, entry=2.4e-6, tick=1e-6, target=0.):
    drain_end = start + drain
    enqueue_end = drain_end + enqueue
    tick_entry = enqueue_end + entry
    return dict(step=step, start=start, drain_end=drain_end, enqueue_end=enqueue_end,
                tick_entry=tick_entry, target=target, end=tick_entry + tick,
                frames_before=step, frames_after=step, error=None)


def child(rows, lateness=(0.,), source_ingestion=False):
    fault = rows[-1]
    return dict(output_frames=len(lateness), automatic_fault_recovery=False,
                output_lateness_seconds=list(lateness),
                dispatch_io=dict(steps=rows[-1]['step'], maximum_drain_seconds=0., maximum_enqueue_seconds=0.,
                                 source_ingestion_profiled=source_ingestion,
                                 first_fault=dict(fault="BridgeFault('Game PCM scheduler late; no catch-up')",
                                                  tick_entry=fault['tick_entry'], target=fault['target'],
                                                  lateness_seconds=fault['tick_entry'] - fault['target'],
                                                  frames_before=0, frames_after=0, stop_confirmed=True,
                                                  context=rows, observed_before_stop_clock_value=True)))


def trace(gap=.0087016, late=.0066075):
    first = row(10, 100., target=100.002)
    second = row(11, first['end'] + .002)
    second['target'] = second['end'] + .0019
    fault = row(12, second['end'] + gap)
    fault['target'] = fault['tick_entry'] - late
    return [first, second, fault]


class Tests(unittest.TestCase):
    def test_gap_is_outside_measured_spans(self):
        result = audit(child(trace()), 'synthetic')
        self.assertEqual(result['status'], 'PASSED_DETERMINISTIC_FROZEN_AUDIT')
        self.assertAlmostEqual(result['gap_seconds'], .0087016, places=12)
        self.assertAlmostEqual(result['entry_delay_seconds'], 4.7e-6, places=12)
        self.assertGreater(result['unmeasured_in_gap_seconds'], .0086)
        self.assertLess(result['measured_share_of_gap'], .001)
        self.assertAlmostEqual(result['fault_lateness_seconds'], .0066075, places=12)
        self.assertAlmostEqual(result['lateness']['maximum'], 0., places=12)
        self.assertTrue(all(result['checks'].values()))

    def test_threshold_is_margin_plus_gate(self):
        result = audit(child(trace()), 'synthetic')
        self.assertAlmostEqual(result['thresholds']['minimum'],
                               result['margins']['minimum'] + GATE, places=12)
        self.assertEqual(result['margins']['count'], 2)
        self.assertGreaterEqual(result['thresholds']['minimum'], GATE)

    def test_no_row_ended_after_target(self):
        self.assertEqual(audit(child(trace()), 'synthetic')['steps_ended_after_target'], 0)

    def test_overlapping_rows_rejected(self):
        rows = trace()
        rows[2]['start'] = rows[1]['end'] - 1e-6
        with self.assertRaises(ValueError):
            audit(child(rows), 'synthetic')

    def test_non_increasing_rows_rejected(self):
        rows = trace()
        rows[2]['start'] = rows[1]['start']
        with self.assertRaises(ValueError):
            audit(child(rows), 'synthetic')

    def test_lateness_mismatch_is_incomplete(self):
        broken = child(trace())
        broken['dispatch_io']['first_fault']['lateness_seconds'] = .001
        result = audit(broken, 'synthetic')
        self.assertEqual(result['status'], 'INCOMPLETE')
        self.assertFalse(result['checks']['fault_lateness_matches_recorded'])

    def test_source_ingestion_flag_required(self):
        result = audit(child(trace(), source_ingestion=True), 'synthetic')
        self.assertFalse(result['checks']['drain_is_not_source_ingestion'])

    def test_missing_fault_entry_rejected(self):
        broken = child(trace())
        broken['dispatch_io']['first_fault']['tick_entry'] = None
        with self.assertRaises(ValueError):
            audit(broken, 'synthetic')


if __name__ == '__main__':
    unittest.main()
