"""Separate the dispatch deadline from USB transport completion.

The earlier candidate used 4 ms for both: a scheduling deadline (`late`) and the
overlapped WriteFile wait. A single cold neutral packet then aborted the run before
any active frame, which measured the transport, not the dispatcher.

This module keeps both bounds explicit and independent. It is pure offline policy:
no device handle, no Win32 call, no output report.
"""
PERIOD_S = 0.004
MAX_DISPATCH_LATE_S = 0.004
MAX_GAP_S = 0.080
TRANSPORT_TIMEOUT_S = 0.050
SLOW_IO_S = 0.004


class TimingFault(RuntimeError):
    pass


def evaluate(due, now, io_elapsed, transport_timeout=TRANSPORT_TIMEOUT_S,
             max_dispatch_late=MAX_DISPATCH_LATE_S):
    """Classify one completed frame. Dispatch and transport are checked separately."""
    for name, value in (('due', due), ('now', now), ('io_elapsed', io_elapsed)):
        if not isinstance(value, (int, float)) or value != value:
            raise ValueError('%s must be a real number' % name)
    if io_elapsed < 0:
        raise ValueError('io_elapsed must not be negative')
    if transport_timeout <= 0:
        raise ValueError('transport_timeout must be positive')
    late = now - due
    if late > max_dispatch_late:
        raise TimingFault('DISPATCH_LATE_%.3fMS' % (late * 1000))
    if io_elapsed > transport_timeout:
        raise TimingFault('TRANSPORT_TIMEOUT_%.3fMS' % (io_elapsed * 1000))
    return dict(late_ms=late * 1000, io_ms=io_elapsed * 1000,
                slow_io=io_elapsed > SLOW_IO_S,
                over_dispatch_budget=late > 0)


def classify(due, now, io_elapsed, transport_timeout=TRANSPORT_TIMEOUT_S):
    """Measurement variant: records dispatch lateness, only transport time is fatal.

    The neutral-only diagnostic has no motor output, so a late scheduling slot is
    data rather than a fault. The transport bound stays hard, because a stuck
    WriteFile is what must stop the run.
    """
    if io_elapsed < 0:
        raise ValueError('io_elapsed must not be negative')
    if io_elapsed > transport_timeout:
        raise TimingFault('TRANSPORT_TIMEOUT_%.3fMS' % (io_elapsed * 1000))
    late = now - due
    return dict(late_ms=late * 1000, io_ms=io_elapsed * 1000,
                slow_io=io_elapsed > SLOW_IO_S,
                over_dispatch_budget=late > MAX_DISPATCH_LATE_S)



class Stats:
    def __init__(self):
        self.count = 0
        self.io = []
        self.late = []

    def add(self, late_ms, io_ms):
        self.count += 1
        self.late.append(late_ms)
        self.io.append(io_ms)

    @staticmethod
    def _summary(values):
        ordered = sorted(values)
        return dict(count=len(ordered), min_ms=ordered[0], median_ms=ordered[len(ordered) // 2],
                    max_ms=ordered[-1])

    def summary(self):
        if not self.count:
            return dict(count=0)
        return dict(count=self.count,
                    dispatch=self._summary(self.late),
                    transport=self._summary(self.io),
                    io_over_4ms=sum(1 for x in self.io if x > SLOW_IO_S * 1000),
                    dispatch_over_4ms=sum(1 for x in self.late if x > MAX_DISPATCH_LATE_S * 1000))


def neutral_frames(count, period=PERIOD_S):
    """Offline plan for the neutral-only diagnostic: (index, due_seconds)."""
    if not isinstance(count, int) or count < 1:
        raise ValueError('count must be a positive integer')
    return [(index, index * period) for index in range(count)]
