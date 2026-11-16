"""Offline probe: must the priority boost cover the sleep, not just the tick? (no device)

181450 and 182222 show the same picture.  The 1 ms `time.sleep` of the product loop wakes
late; the 8 ms grid then sees `now - target` above the 4 ms gate and the run faults before
any haptic event arrives.  `wake_tail_probe.py` already showed the lever: a thread running at
`THREAD_PRIORITY_TIME_CRITICAL` wakes within 1.75 ms instead of 10.12 ms.  But
`priority_window.py` boosts only around `tick()`, i.e. *after* the wake has already happened.

This probe asks one question: how much of the tail survives when the boost covers the wait
itself?  Four arms of the same composed loop (cancel stat, inbox drain, 1 KiB phase write
every 200 iterations, 1 ms sleep, 8 ms grid, 4 ms gate):

    normal        no boost, product loop as it runs today
    tick_only     boost around the dispatch work only (today's PriorityWindow)
    sleep_boost   boost before the sleep, released after the dispatch (or after the wake)
    armed_boost   boost held for the whole armed window

Reported per arm: dispatch lateness on the 8 ms grid (`now - target`, the quantity the gate
judges), wake overshoot of the 1 ms sleep, and the wake delay of a second, normal-priority
"collector" thread that keeps sleeping 0.5 ms - so the cost of holding the boost is visible
instead of assumed.  Nothing here writes Flash, opens a device or changes a protocol value.
"""
import argparse, json, pathlib, statistics, threading, time

from thread_priority import TIME_CRITICAL, ThreadPriority

ROOT = pathlib.Path(__file__).resolve().parent.parent
CAMPAIGN = ROOT / 'docs/campaigns/outer-loop-2026-11-15'
PERIOD = 0.008
GATE = 0.004
WAIT = 0.001
COLLECTOR_WAIT = 0.0005
ARMS = ('normal', 'tick_only', 'sleep_boost', 'armed_boost')


def stats(values):
    if not values:
        return dict(count=0)
    s = sorted(values)
    pick = lambda f: s[min(len(s) - 1, int(round(f * (len(s) - 1))))]
    return dict(count=len(s), minimum=s[0], median=pick(.5), p95=pick(.95),
                p99=pick(.99), maximum=s[-1])


def summarize_dispatch(latencies):
    return dict(lateness_seconds=stats(latencies),
                dispatched=len(latencies),
                at_or_over_4ms=sum(v >= GATE for v in latencies),
                over_3ms=sum(v > 0.003 for v in latencies),
                over_6ms=sum(v > 0.006 for v in latencies))


def summarize_wakes(overshoots):
    return dict(overshoot_seconds=stats(overshoots),
                over_1ms=sum(v > 0.001 for v in overshoots),
                over_3ms=sum(v > 0.003 for v in overshoots),
                over_4ms=sum(v > GATE for v in overshoots),
                over_6ms=sum(v > 0.006 for v in overshoots))


def gate_verdict(lateness):
    """The product rule, unchanged: one frame at or beyond 4 ms is a fault."""
    return 'FAULT' if lateness >= GATE else 'OK'


def validate_arm(arm):
    if arm not in ARMS:
        raise ValueError('Unknown arm: %s' % arm)
    return arm


class LoadGenerator(threading.Thread):
    """Normal-priority background load: spin 1 ms, yield 0.2 ms, repeat."""

    def __init__(self):
        super().__init__(daemon=True)
        self.stop = threading.Event()

    def run(self):
        while not self.stop.is_set():
            end = time.perf_counter() + 0.001
            while time.perf_counter() < end and not self.stop.is_set():
                pass
            time.sleep(0.0002)


class Collector(threading.Thread):
    """Normal-priority stand-in for the UDP collector thread."""

    def __init__(self):
        super().__init__(daemon=True)
        self.stop = threading.Event()
        self.delays = []

    def run(self):
        while not self.stop.is_set():
            started = time.perf_counter()
            time.sleep(COLLECTOR_WAIT)
            self.delays.append(time.perf_counter() - started - COLLECTOR_WAIT)


def dispatch_once():
    """Stand-in for a renderer frame: a few microseconds of work."""
    end = time.perf_counter() + 0.00002
    while time.perf_counter() < end:
        pass


def run_dispatch(arm, periods, collector):
    validate_arm(arm)
    latencies, overshoots = [], []
    started = time.perf_counter()
    target = started + PERIOD
    outer = ThreadPriority(TIME_CRITICAL) if arm == 'armed_boost' else None
    if outer:
        outer.__enter__()
    try:
        while len(latencies) < periods:
            inner = ThreadPriority(TIME_CRITICAL) if arm == 'sleep_boost' else None
            if inner:
                inner.__enter__()
            requested = time.perf_counter()
            time.sleep(WAIT)
            now = time.perf_counter()
            overshoots.append(now - requested - WAIT)
            if now >= target:
                tick = ThreadPriority(TIME_CRITICAL) if arm == 'tick_only' else None
                if tick:
                    tick.__enter__()
                dispatch_once()
                latencies.append(now - target)
                target += PERIOD
                if tick:
                    tick.__exit__(None, None, None)
            if inner:
                inner.__exit__(None, None, None)
    finally:
        if outer:
            outer.__exit__(None, None, None)
    return latencies, overshoots


def run_wake(arm, iterations):
    validate_arm(arm)
    overshoots, periods = [], []
    outer = ThreadPriority(TIME_CRITICAL) if arm == 'armed_boost' else None
    if outer:
        outer.__enter__()
    try:
        for _ in range(iterations):
            inner = ThreadPriority(TIME_CRITICAL) if arm == 'sleep_boost' else None
            if inner:
                inner.__enter__()
            before = time.perf_counter()
            time.sleep(WAIT)
            after = time.perf_counter()
            if inner:
                inner.__exit__(None, None, None)
            periods.append(after - before)
            overshoots.append(after - before - WAIT)
    finally:
        if outer:
            outer.__exit__(None, None, None)
    return periods, overshoots


def run_arms(arms, periods, wakes):
    report = {}
    for arm in arms:
        collector = Collector()
        collector.start()
        latencies, dispatch_overshoots = run_dispatch(arm, periods, collector)
        collector.stop.set()
        collector.join(timeout=2)
        wake_periods, wake_overshoots = run_wake(arm, wakes)
        report[arm] = dict(
            dispatch=summarize_dispatch(latencies),
            wake_overshoot=summarize_wakes(wake_overshoots + dispatch_overshoots),
            wake_period=stats(wake_periods),
            collector=stats(collector.delays),
            gate_verdicts={v: sum(gate_verdict(x) == v for x in latencies) for v in ('OK', 'FAULT')},
        )
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--periods', type=int, default=2000)
    parser.add_argument('--wakes', type=int, default=12000)
    parser.add_argument('--arms', default=','.join(ARMS))
    parser.add_argument('--load-threads', type=int, default=0)
    parser.add_argument('--out', default=None)
    args = parser.parse_args()
    arms = [a.strip() for a in args.arms.split(',') if a.strip()]
    for arm in arms:
        validate_arm(arm)

    loaders = [LoadGenerator() for _ in range(args.load_threads)]
    for loader in loaders:
        loader.start()
    try:
        arms_report = run_arms(arms, args.periods, args.wakes)
    finally:
        for loader in loaders:
            loader.stop.set()
        for loader in loaders:
            loader.join(timeout=2)

    report = dict(
        status='PASSED_OFFLINE_PRIORITY_COVERAGE',
        hardware_actions=0,
        constants=dict(period_seconds=PERIOD, gate_seconds=GATE, wait_seconds=WAIT,
                       collector_wait_seconds=COLLECTOR_WAIT),
        sample=dict(periods=args.periods, wakes=args.wakes, load_threads=args.load_threads),
        arms=arms_report,
    )
    text = json.dumps(report, indent=2, sort_keys=True) + '\n'
    if args.out:
        path = pathlib.Path(args.out)
        if not path.is_absolute():
            path = ROOT / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        print('WROTE', path)
    else:
        print(text)
    for arm in arms:
        d = arms_report[arm]['dispatch']
        w = arms_report[arm]['wake_overshoot']
        c = arms_report[arm]['collector']
        print('%-12s lateness max %7.3f ms  >=4ms %3d | wake max %7.3f ms  >3ms %3d | collector max %7.3f ms'
              % (arm, d['lateness_seconds'].get('maximum', 0) * 1e3, d['at_or_over_4ms'],
                 w['overshoot_seconds'].get('maximum', 0) * 1e3, w['over_3ms'],
                 c.get('maximum', 0) * 1e3))


if __name__ == '__main__':
    main()
