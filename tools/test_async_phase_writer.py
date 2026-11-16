"""Offline proofs for the async phase writer: ordering, non-blocking, retry, flush."""
import os
import pathlib
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import async_phase_path as module

try:
    import loop_probe_session
except ImportError:  # pragma: no cover
    loop_probe_session = None


class Tests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.target = pathlib.Path(self.directory) / 'phase.json'

    def tearDown(self):
        os.environ.pop('FLYDIGI_ASYNC_PHASE', None)

    def test_writes_are_ordered_and_flushed(self):
        writer = module.AsyncPhasePath(self.target)
        for index in range(50):
            writer.write_text('{"n":%d}' % index)
        self.assertTrue(writer.flush())
        stats = writer.close()
        self.assertEqual(stats['error_count'], 0)
        self.assertEqual(self.target.read_text(), '{"n":49}')

    def test_write_never_blocks_the_caller(self):
        writer = module.AsyncPhasePath(self.target)
        began = time.perf_counter()
        for _ in range(20):
            writer.write_text('x' * 1024)
        self.assertLess(time.perf_counter() - began, .2)
        writer.close()

    def test_sharing_violation_is_retried(self):
        writer = module.AsyncPhasePath(self.target)
        calls = {'n': 0}
        real = writer._inner

        class Flaky(object):
            def write_text(self, data):
                calls['n'] += 1
                if calls['n'] < 3:
                    raise PermissionError(13, 'denied')
                return real.write_text(data)

        writer._inner = Flaky()
        writer.write_text('payload')
        self.assertTrue(writer.flush())
        writer.close()
        self.assertEqual(self.target.read_text(), 'payload')

    def test_persistent_failure_is_recorded_not_raised(self):
        writer = module.AsyncPhasePath(self.target)

        class Broken(object):
            def write_text(self, data):
                raise PermissionError(13, 'denied')

        writer._inner = Broken()
        writer.write_text('payload')
        writer.flush(timeout=.5)
        stats = writer.close()
        self.assertGreaterEqual(stats['error_count'], 1)

    def test_disabled_by_default(self):
        self.assertFalse(module.enabled())
        os.environ['FLYDIGI_ASYNC_PHASE'] = '1'
        self.assertTrue(module.enabled())

    def test_close_is_idempotent(self):
        writer = module.AsyncPhasePath(self.target)
        self.assertIsInstance(writer.close(), dict)
        self.assertIsInstance(writer.close(), dict)


if __name__ == '__main__':
    unittest.main()
