"""Bounded thread-priority boost for the dispatch loop (candidate helper; offline).

The 20k-iteration wake-tail probe (`wake_tail_probe.py`) shows the 8-10 ms wake delays of
the current loop disappear when the waiting thread runs at `THREAD_PRIORITY_TIME_CRITICAL`:
maximum overshoot falls from 10.12 ms to 1.75 ms and no overshoot exceeds 3 ms, while the
high-resolution timer alone does not help.  This module isolates that one lever so a
candidate runner can apply it for a bounded window and always restore the old priority.

It changes no protocol value: the 8 ms grid, the 4 ms gate and the 80 ms silence guard stay
where they are.  A boost that is not released is a bug, so every path restores.
"""
import contextlib, ctypes

THREAD_PRIORITY_ERROR_RETURN = 0x7FFFFFFF
NORMAL = 0
ABOVE_NORMAL = 1
HIGHEST = 2
TIME_CRITICAL = 15


def kernel32():
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentThread.restype = ctypes.c_void_p
    kernel.GetThreadPriority.argtypes = [ctypes.c_void_p]
    kernel.GetThreadPriority.restype = ctypes.c_int
    kernel.SetThreadPriority.argtypes = [ctypes.c_void_p, ctypes.c_int]
    kernel.SetThreadPriority.restype = ctypes.c_bool
    return kernel


class ThreadPriority:
    """Context manager that raises the current thread and always restores it."""

    def __init__(self, level=TIME_CRITICAL, kernel=None):
        if level not in (NORMAL, ABOVE_NORMAL, HIGHEST, TIME_CRITICAL):
            raise ValueError('Unsupported priority level')
        self.kernel = kernel or kernel32()
        self.level = level
        self.original = None

    def __enter__(self):
        thread = self.kernel.GetCurrentThread()
        previous = self.kernel.GetThreadPriority(thread)
        if previous == THREAD_PRIORITY_ERROR_RETURN:
            raise OSError(ctypes.get_last_error(), 'GetThreadPriority failed')
        if not self.kernel.SetThreadPriority(thread, self.level):
            raise OSError(ctypes.get_last_error(), 'SetThreadPriority failed')
        self.original = previous
        return self

    def __exit__(self, *exc_info):
        if self.original is not None:
            self.kernel.SetThreadPriority(self.kernel.GetCurrentThread(), self.original)
            self.original = None
        return False

    @property
    def active(self):
        return self.original is not None


def boosted(level=TIME_CRITICAL, kernel=None):
    return ThreadPriority(level=level, kernel=kernel)
