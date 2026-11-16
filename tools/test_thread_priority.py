"""Synthetic tests for the bounded thread-priority helper (no Win32 calls)."""
import unittest
import thread_priority as tp


class FakeKernel:
    def __init__(self, previous=tp.NORMAL, fail_set=False, fail_get=False):
        self.previous, self.fail_set, self.fail_get = previous, fail_set, fail_get
        self.set_calls, self.get_calls = [], 0

    def GetCurrentThread(self):
        return 1

    def GetThreadPriority(self, thread):
        self.get_calls += 1
        return tp.THREAD_PRIORITY_ERROR_RETURN if self.fail_get else self.previous

    def SetThreadPriority(self, thread, level):
        self.set_calls.append(level)
        return not self.fail_set


class Tests(unittest.TestCase):
    def test_boost_then_restore(self):
        kernel = FakeKernel()
        with tp.ThreadPriority(tp.TIME_CRITICAL, kernel=kernel) as boost:
            self.assertTrue(boost.active)
        self.assertEqual(kernel.set_calls, [tp.TIME_CRITICAL, tp.NORMAL])
        self.assertFalse(boost.active)

    def test_restore_happens_on_exception(self):
        kernel = FakeKernel()
        with self.assertRaises(RuntimeError):
            with tp.ThreadPriority(tp.HIGHEST, kernel=kernel):
                raise RuntimeError('loop failed')
        self.assertEqual(kernel.set_calls, [tp.HIGHEST, tp.NORMAL])

    def test_get_failure_is_loud_and_does_not_change_priority(self):
        kernel = FakeKernel(fail_get=True)
        with self.assertRaises(OSError):
            tp.ThreadPriority(tp.TIME_CRITICAL, kernel=kernel).__enter__()
        self.assertEqual(kernel.set_calls, [])

    def test_set_failure_is_loud(self):
        kernel = FakeKernel(fail_set=True)
        with self.assertRaises(OSError):
            tp.ThreadPriority(tp.TIME_CRITICAL, kernel=kernel).__enter__()

    def test_rejects_unknown_level(self):
        with self.assertRaises(ValueError):
            tp.ThreadPriority(99, kernel=FakeKernel())

    def test_default_level_is_time_critical(self):
        self.assertEqual(tp.ThreadPriority(kernel=FakeKernel()).level, tp.TIME_CRITICAL)


if __name__ == '__main__':
    unittest.main()
