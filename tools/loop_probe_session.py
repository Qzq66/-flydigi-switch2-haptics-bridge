"""Offline probe: where does the loop's >4 ms tick-entry lateness actually come from?

The spin candidate proved the wait tail is gone (3181 dispatched frames, none at or over
4 ms) yet the gate still fired on a tick that never dispatched.  The gate measures
`now - target` when `tick()` is entered, so the remaining budget is the loop *body*:
draining the inbox, the synchronous phase write, the fault and cancel checks.

This module attributes that budget without copying the frozen loop:

- `wrap(base)` subclasses the session; `tick()` records entry lateness, the gap since the
  previous tick returned (the whole body), and the tick's own duration.  The ring is merged
  into the child report through `summary()`.
- `ProbePath` replaces the phase path handed to the child; it times every `write_text`, so
  the synchronous publish cost is measured separately instead of guessed.

Nothing here changes a protocol value, a deadline or a gate.  Enable with
FLYDIGI_LOOP_PROBE=1; disabled, the wrapper is a transparent subclass and records nothing.
"""
import collections
import os
import pathlib
import time

_RECORDS = collections.deque(maxlen=256)
_PUBLISHES = collections.deque(maxlen=256)


def enabled():
    return os.environ.get('FLYDIGI_LOOP_PROBE') == '1'


def publish_stats():
    values = list(_PUBLISHES)
    if not values:
        return dict(count=0, maximum_seconds=None, median_seconds=None)
    ordered = sorted(values)
    return dict(count=len(values), maximum_seconds=max(values),
                median_seconds=ordered[len(ordered) // 2])


def probe_stats():
    records = list(_RECORDS)
    if not records:
        return dict(count=0)
    lateness = [r['lateness_seconds'] for r in records if r['lateness_seconds'] is not None]
    gaps = [r['gap_seconds'] for r in records if r['gap_seconds'] is not None]
    durations = [r['tick_seconds'] for r in records]
    return dict(count=len(records), lateness_count=len(lateness),
                lateness_max_seconds=max(lateness) if lateness else None,
                lateness_over_4ms=sum(1 for v in lateness if v >= .004),
                gap_max_seconds=max(gaps) if gaps else None,
                tick_max_seconds=max(durations),
                last=[dict(r) for r in records[-8:]])


class ProbePath(object):
    """Drop-in for the phase `pathlib.Path` that times each `write_text`."""

    def __init__(self, inner):
        self._inner = pathlib.Path(inner)

    def write_text(self, data, **kwargs):
        began = time.perf_counter()
        try:
            return self._inner.write_text(data, **kwargs)
        finally:
            if enabled():
                _PUBLISHES.append(time.perf_counter() - began)

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def __fspath__(self):
        return str(self._inner)

    def __str__(self):
        return str(self._inner)


def wrap(base):
    class LoopProbeSession(base):
        def __init__(self, *args, **kwargs):
            base.__init__(self, *args, **kwargs)
            self.loop_probe_enabled = enabled()
            self._loop_probe_last_exit = None

        def tick(self):
            if not self.loop_probe_enabled:
                return base.tick(self)
            entered = time.perf_counter()
            target = getattr(self, 'target', None)
            lateness = None if target is None else entered - target
            gap = None if self._loop_probe_last_exit is None else entered - self._loop_probe_last_exit
            try:
                return base.tick(self)
            finally:
                left = time.perf_counter()
                self._loop_probe_last_exit = left
                _RECORDS.append(dict(lateness_seconds=lateness, gap_seconds=gap,
                                     tick_seconds=left - entered))

        def summary(self):
            report = base.summary(self)
            if self.loop_probe_enabled:
                report['loop_probe'] = probe_stats()
            return report

    LoopProbeSession.__name__ = 'LoopProbe' + base.__name__
    LoopProbeSession.__qualname__ = LoopProbeSession.__name__
    return LoopProbeSession
