"""Offline proofs for the entry-level phase writer shipped in the frozen adapter.

`dispatch_windows_entry.AsyncPhasePath` publishes through `PhasePublisher`, whose writer
callback retries a Windows sharing violation that the Tk reader can provoke with an atomic
replace.  These tests pin that retry contract directly.
"""
import json
import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import dispatch_windows_entry as entry


class Sink(object):
    def __init__(self, writer):
        self.writer = writer
        self.phases = []

    def publish(self, phase, **fields):
        self.phases.append(phase)
        self.writer(json.dumps(dict(phase=phase, clock='monotonic', **fields)))


class Tests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.directory = tempfile.mkdtemp()
        self.path = pathlib.Path(self.directory) / 'phase.json'
        self.writer = entry.AsyncPhasePath(self.path, publisher_factory=Sink)

    def test_sharing_violation_is_retried_then_written(self):
        calls = {'n': 0}
        real = pathlib.Path.replace

        def flaky(source, target):
            calls['n'] += 1
            if calls['n'] < 3:
                raise PermissionError(13, 'denied')
            return real(source, target)

        with mock.patch.object(pathlib.Path, 'replace', flaky):
            self.writer._write(json.dumps(dict(phase='ARMED', clock='monotonic')))
        self.assertEqual(calls['n'], 3)
        self.assertEqual(json.loads(self.path.read_text())['phase'], 'ARMED')

    def test_persistent_failure_surfaces(self):
        with mock.patch.object(pathlib.Path, 'replace',
                               side_effect=PermissionError(13, 'denied')):
            with self.assertRaises(PermissionError):
                self.writer._write('{}')
        self.assertFalse(self.path.exists())

    def test_other_errors_are_not_retried(self):
        calls = {'n': 0}

        def broken(source, target):
            calls['n'] += 1
            raise OSError(28, 'disk full')

        with mock.patch.object(pathlib.Path, 'replace', broken):
            with self.assertRaises(OSError):
                self.writer._write('{}')
        self.assertEqual(calls['n'], 1)

    def test_write_text_rejects_wrong_clock(self):
        with self.assertRaises(ValueError):
            self.writer.write_text(json.dumps(dict(phase='ARMED', clock='wall')))


if __name__ == '__main__':
    unittest.main()
