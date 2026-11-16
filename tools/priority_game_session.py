"""Wrap the frozen ``GameSession`` so its dispatch tick runs inside the priority window.

The product child builds ``GameSession`` directly (``run_sustained_game_g61.child``), so the
entry-level ``ObservedGame`` wrapper never saw the real trial path: the 63rd-generation run
armed and released with no priority boost at all.  This module closes that gap at the object
the child actually uses.

The wrapper keeps every frozen rule intact and only changes the host scheduling class of the
thread while ``tick()`` is executing.  The boost is gated by the same environment key the
entry sets (``FLYDIGI_PRIORITY_WINDOW=1``), so the plain child path and the generation-61
path behave exactly as before.
"""

import os

import priority_window

KEY = 'FLYDIGI_PRIORITY_WINDOW'


def enabled():
    return os.environ.get(KEY) == '1'


def wrap(base):
    """Return a ``GameSession`` subclass whose ``tick`` is polarity-safe."""

    class PriorityGameSession(base):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._priority = priority_window.PriorityWindow() if enabled() else None

        def tick(self):
            if self._priority is None:
                return super().tick()
            return self._priority.step(super().tick)

        def summary(self):
            summary = super().summary() if hasattr(base, 'summary') else {}
            if self._priority is not None:
                summary['priority_window'] = self._priority.summary()
            return summary

    return PriorityGameSession
