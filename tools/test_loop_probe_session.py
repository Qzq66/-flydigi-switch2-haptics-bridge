"""Offline proofs for the loop-body probe: attribution without touching the frozen loop."""
import os
import pathlib
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import loop_probe_session as probe


class FakeBase(object):
    def __init__(self, latency=0.0):
        self.target = None
        self.latency = latency
        self.calls = 0

    def tick(self):
        self.calls += 1
        time.sleep(self.latency)

    def summary(self):
        return dict(frames=self.calls)


class Tests(unittest.TestCase):
    def setUp(self):
        os.environ.pop('FLYDIGI_LOOP_PROBE', None)
        probe._RECORDS.clear()
        probe._PUBLISHES.clear()

    def tearDown(self):
        os.environ.pop('FLYDIGI_LOOP_PROBE', None)

    def test_disabled_wrapper_is_transparent(self):
        session = probe.wrap(FakeBase)()
        session.target = time.perf_counter()
        session.tick()
        self.assertEqual(session.summary(), dict(frames=1))
        self.assertEqual(probe.probe_stats(), dict(count=0))

    def test_enabled_wrapper_records_entry_lateness_and_gap(self):
        os.environ['FLYDIGI_LOOP_PROBE'] = '1'
        session = probe.wrap(FakeBase)()
        session.target = time.perf_counter() - .005  # entry five milliseconds late
        session.tick()
        session.target = time.perf_counter() - .005
        session.tick()
        stats = probe.probe_stats()
        self.assertEqual(stats['count'], 2)
        self.assertEqual(stats['lateness_count'], 2)
        self.assertGreaterEqual(stats['lateness_max_seconds'], .004)
        self.assertEqual(stats['lateness_over_4ms'], 2)
        self.assertIsNotNone(stats['gap_max_seconds'])
        self.assertTrue(session.summary()['loop_probe']['count'] == 2)

    def test_tick_duration_is_recorded(self):
        os.environ['FLYDIGI_LOOP_PROBE'] = '1'
        session = probe.wrap(FakeBase)(latency=.02)
        session.tick()
        self.assertGreaterEqual(probe.probe_stats()['tick_max_seconds'], .015)

    def test_probe_path_times_the_write_and_still_writes(self):
        os.environ['FLYDIGI_LOOP_PROBE'] = '1'
        directory = tempfile.mkdtemp()
        target = pathlib.Path(directory) / 'phase.json'
        wrapped = probe.ProbePath(target)
        wrapped.write_text('{"phase":"ARMED"}')
        self.assertEqual(target.read_text(), '{"phase":"ARMED"}')
        stats = probe.publish_stats()
        self.assertEqual(stats['count'], 1)
        self.assertIsNotNone(stats['maximum_seconds'])

    def test_probe_path_delegates_path_operations(self):
        directory = tempfile.mkdtemp()
        wrapped = probe.ProbePath(pathlib.Path(directory) / 'phase.json')
        self.assertEqual(str(wrapped), str(pathlib.Path(directory) / 'phase.json'))
        self.assertEqual(wrapped.with_suffix('.cancel').name, 'phase.cancel')

    def test_disabled_probe_path_does_not_record(self):
        directory = tempfile.mkdtemp()
        wrapped = probe.ProbePath(pathlib.Path(directory) / 'phase.json')
        wrapped.write_text('x')
        self.assertEqual(probe.publish_stats()['count'], 0)


if __name__ == '__main__':
    unittest.main()
