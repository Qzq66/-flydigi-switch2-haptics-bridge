"""Synthetic tests for the bounded priority window (no Win32 calls)."""
import unittest
from priority_window import PriorityWindow
from thread_priority import ThreadPriority, HIGHEST, NORMAL, TIME_CRITICAL


class FakeKernel:
    def __init__(self, current=NORMAL):
        self.current = current
        self.levels = []

    def GetCurrentThread(self):
        return 1

    def GetThreadPriority(self, thread):
        return self.current

    def SetThreadPriority(self, thread, level):
        self.levels.append(level)
        self.current = level
        return True


def factory(kernel):
    return lambda: ThreadPriority(TIME_CRITICAL, kernel=kernel)


class Tests(unittest.TestCase):
    def test_disabled_runs_action_without_boosting(self):
        kernel = FakeKernel()
        window = PriorityWindow(enabled=False, boost_factory=factory(kernel))
        self.assertEqual(window.step(lambda: 7), 7)
        self.assertEqual(kernel.levels, [])
        self.assertEqual(window.steps, 0)
        self.assertFalse(window.summary()['enabled'])

    def test_boost_held_during_action_and_restored_after(self):
        kernel = FakeKernel()
        window = PriorityWindow(boost_factory=factory(kernel))
        seen = []
        window.step(lambda: seen.append(kernel.current))
        self.assertEqual(seen, [TIME_CRITICAL])
        self.assertEqual(kernel.current, NORMAL)

    def test_exception_does_not_leave_thread_boosted(self):
        kernel = FakeKernel()
        window = PriorityWindow(boost_factory=factory(kernel))
        with self.assertRaises(RuntimeError):
            window.step(lambda: (_ for _ in ()).throw(RuntimeError('late')))
        self.assertEqual(kernel.current, NORMAL)
        self.assertEqual(window.steps, 1)

    def test_records_hold_time(self):
        kernel = FakeKernel()
        window = PriorityWindow(boost_factory=factory(kernel))
        for _ in range(3):
            window.step(lambda: None)
        self.assertEqual(window.steps, 3)
        self.assertGreater(window.max_hold_ms, 0.0)

    def test_level_is_forwarded(self):
        kernel = FakeKernel()
        window = PriorityWindow(HIGHEST, boost_factory=lambda: ThreadPriority(HIGHEST, kernel=kernel))
        window.step(lambda: None)
        self.assertEqual(kernel.levels, [HIGHEST, NORMAL])
        self.assertEqual(window.summary()['level'], HIGHEST)


if __name__ == '__main__':
    unittest.main()
