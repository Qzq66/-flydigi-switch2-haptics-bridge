"""Offline wake-tail probe: which Windows wait primitive bounds the tail? (no device)

The frozen faults show a single loop wake arriving 8.7 ms late while the pending frame
deadline was only 2.1 ms away, so `start - target` passed the 4 ms gate.  This probe
compares four ways to wait 1 ms in the same composed loop (cancel stat, inbox drain,
1 KiB phase write every 200 iterations):

    sleep_1ms             timeBeginPeriod(1) + time.sleep(.001)      (current product loop)
    sleep_1ms_priority    same + THREAD_PRIORITY_TIME_CRITICAL
    waitable_highres      CreateWaitableTimerExW HIGH_RESOLUTION, relative 1 ms
    waitable_highres_priority  same + THREAD_PRIORITY_TIME_CRITICAL

Reported per arm: loop period and `overshoot` = wake time minus the time the wait was
asked to end.  Overshoot is the quantity the product gate actually cares about.
"""
import argparse, ctypes, json, pathlib, statistics, tempfile, time

ROOT = pathlib.Path(__file__).resolve().parent.parent
CAMPAIGN = ROOT / 'docs/campaigns/outer-loop-2026-11-15'
CREATE_WAITABLE_TIMER_HIGH_RESOLUTION = 0x00000002
WAIT_OBJECT_0 = 0
THREAD_PRIORITY_TIME_CRITICAL = 15
ONE_MS_100NS = 10_000


def win32():
    k = ctypes.WinDLL('kernel32', use_last_error=True)
    k.CreateWaitableTimerExW.restype = ctypes.c_void_p
    k.CreateWaitableTimerExW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_ulong, ctypes.c_ulong]
    k.SetWaitableTimer.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int64), ctypes.c_long,
                                   ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
    k.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    k.CloseHandle.argtypes = [ctypes.c_void_p]
    k.GetCurrentThread.restype = ctypes.c_void_p
    k.GetThreadPriority.argtypes = [ctypes.c_void_p]
    k.SetThreadPriority.argtypes = [ctypes.c_void_p, ctypes.c_int]
    k.timeBeginPeriod.argtypes = [ctypes.c_uint]
    k.timeEndPeriod.argtypes = [ctypes.c_uint]
    return k


def stats(values):
    s = sorted(values)
    pick = lambda f: s[min(len(s) - 1, int(round(f * (len(s) - 1))))]
    return dict(count=len(s), minimum=s[0], median=pick(.5), p95=pick(.95),
                p99=pick(.99), maximum=s[-1])


def summarize(periods, overshoots):
    return dict(period_seconds=stats(periods), overshoot_seconds=stats(overshoots),
                periods_over_4ms=sum(v > .004 for v in periods),
                periods_over_6ms=sum(v > .006 for v in periods),
                overshoots_over_1ms=sum(v > .001 for v in overshoots),
                overshoots_over_3ms=sum(v > .003 for v in overshoots),
                overshoots_over_5ms=sum(v > .005 for v in overshoots))


class HighResTimer:
    def __init__(self, kernel):
        self.kernel = kernel
        self.handle = kernel.CreateWaitableTimerExW(None, None, CREATE_WAITABLE_TIMER_HIGH_RESOLUTION, 0x1F0003)
        if not self.handle:
            raise OSError(ctypes.get_last_error(), 'CreateWaitableTimerExW failed')

    def wait(self, seconds):
        due = ctypes.c_int64(-int(seconds * 1e7))
        if not self.kernel.SetWaitableTimer(self.handle, ctypes.byref(due), 0, None, None, None):
            raise OSError(ctypes.get_last_error(), 'SetWaitableTimer failed')
        if self.kernel.WaitForSingleObject(self.handle, 0xFFFFFFFF) != WAIT_OBJECT_0:
            raise OSError(ctypes.get_last_error(), 'WaitForSingleObject failed')

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


def composed_loop(wait, iterations, work_dir):
    """Same composition as the earlier host probe, so periods are comparable."""
    marker = work_dir / 'composed.phase'
    cancel = work_dir / 'composed.cancel'
    periods, overshoots = [], []
    previous = None
    for index in range(iterations):
        if cancel.exists():
            raise RuntimeError('Unexpected cancel marker')
        if index % 200 == 0:
            marker.write_text('{"phase":"ARMED","frame":%d}' % index)
        requested = time.perf_counter() + .001
        wait(.001)
        wake = time.perf_counter()
        overshoots.append(wake - requested)
        if previous is not None:
            periods.append(wake - previous)
        previous = wake
    return periods, overshoots


def run_arm(kernel, timer, priority, iterations, work_dir):
    period_set = kernel.timeBeginPeriod(1)
    original = None
    thread = kernel.GetCurrentThread()
    try:
        if priority:
            original = kernel.GetThreadPriority(thread)
            if not kernel.SetThreadPriority(thread, THREAD_PRIORITY_TIME_CRITICAL):
                raise OSError(ctypes.get_last_error(), 'SetThreadPriority failed')
        periods, overshoots = composed_loop(timer.wait if timer else time.sleep, iterations, work_dir)
    finally:
        if original is not None:
            kernel.SetThreadPriority(thread, original)
        kernel.timeEndPeriod(1)
    result = summarize(periods, overshoots)
    result.update(timer_request=period_set, priority_raised=original is not None,
                  timer='waitable_highres' if timer else 'sleep')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--iterations', type=int, default=20000)
    parser.add_argument('--output', type=pathlib.Path)
    args = parser.parse_args()
    kernel = win32()
    work_dir = pathlib.Path(tempfile.mkdtemp(prefix='wake-tail-'))
    arms, notes = {}, []
    timer = HighResTimer(kernel)
    try:
        for name, use_timer, priority in (('sleep_1ms', False, False),
                                          ('sleep_1ms_priority', False, True),
                                          ('waitable_highres', True, False),
                                          ('waitable_highres_priority', True, True)):
            arms[name] = run_arm(kernel, timer if use_timer else None, priority, args.iterations, work_dir)
    finally:
        timer.close()
    report = dict(status='COMPLETED', hardware_actions=0, network_actions=0,
                  iterations=args.iterations,
                  scope='Pure-host composed wait loop; no device, network or hardware entry',
                  notes=notes, arms=arms)
    out = args.output or CAMPAIGN / ('wake-tail-' + time.strftime('%Y%m%d-%H%M%S') + '.json')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding='utf-8')
    for name, arm in arms.items():
        print('%-26s period max=%6.2fms overshoot max=%6.2fms >1ms=%4d >3ms=%3d' % (
            name, arm['period_seconds']['maximum'] * 1e3, arm['overshoot_seconds']['maximum'] * 1e3,
            arm['overshoots_over_1ms'], arm['overshoots_over_3ms']))
    print(out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
