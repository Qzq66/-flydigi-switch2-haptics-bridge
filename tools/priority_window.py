"""Bounded priority window around the armed dispatch step (candidate; offline).

`thread_priority.ThreadPriority` raises and restores a single thread; this wraps it around
exactly one call, so a runner can claim the boost only for the window in which a late wake
would turn into a fault.  The window is measured, so an integration can prove the boost was
actually held across the wait instead of merely requested.

Contract:
  * disabled window -> the action runs untouched;
  * enabled window  -> boost, run, always restore, record hold time;
  * an exception in the action must not leave the thread boosted.
"""
import time
from thread_priority import ThreadPriority, TIME_CRITICAL


class PriorityWindow:
    def __init__(self, level=TIME_CRITICAL, enabled=True, boost_factory=None):
        self.level = level
        self.enabled = enabled
        self._factory = boost_factory or (lambda: ThreadPriority(level))
        self.steps = 0
        self.max_hold_ms = 0.0
        self.last_hold_ms = 0.0

    def step(self, action):
        if not self.enabled:
            return action()
        window = self._factory()
        window.__enter__()
        started = time.perf_counter()
        try:
            return action()
        finally:
            hold_ms = (time.perf_counter() - started) * 1000.0
            self.steps += 1
            self.last_hold_ms = hold_ms
            self.max_hold_ms = max(self.max_hold_ms, hold_ms)
            window.__exit__(None, None, None)

    def summary(self):
        return dict(level=self.level, enabled=self.enabled, steps=self.steps,
                    max_hold_ms=self.max_hold_ms, last_hold_ms=self.last_hold_ms)
