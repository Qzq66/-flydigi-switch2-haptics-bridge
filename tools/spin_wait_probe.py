"""Offline: can a short spin absorb the wake tail under the 4 ms gate? (no device)

Under load the 1 ms sleep loop wakes 5-9 ms late and a single frame at or beyond 4 ms faults
the whole run (`priority_coverage_probe.py`, arms normal / armed_boost).  Raising the thread
priority halves the tail but cannot remove it.  The remaining lever is to stop *waiting on the
OS* for the last part of the gap: sleep until a margin before the deadline, then spin.

Arms (all on the unchanged 8 ms grid and 4 ms gate):

    baseline         product loop: take the 1 ms sleep, dispatch when now >= target
    spin_1ms         sleep until target - 1 ms, spin the last 1 ms
    spin_2ms         sleep until target - 2 ms, spin the last 2 ms
    spin_3ms         sleep until target - 3 ms, spin the last 3 ms
    spin_2ms_boost   as spin_2ms, but the spin runs at THREAD_PRIORITY_TIME_CRITICAL

Reported per arm: dispatch lateness (the gated quantity), spin duration, the loop thread's CPU
share (thread_time / wall, so a spin is not free), and the wake delay of a normal-priority
collector thread running alongside.  Nothing here touches a device or a protocol value.
"""
import argparse, json, pathlib, time

from priority_coverage_probe import (COLLECTOR_WAIT, Collector, GATE, LoadGenerator,
                                     PERIOD, WAIT, stats)
from thread_priority import TIME_CRITICAL, ThreadPriority

ROOT = pathlib.Path(__file__).resolve().parent.parent
CAMPAIGN = ROOT / 'docs/campaigns/outer-loop-2026-11-15'
MARGINS = dict(baseline=None, spin_1ms=0.001, spin_2ms=0.002, spin_3ms=0.003,
               spin_2ms_boost=0.002)
BOOST_ARMS = ('spin_2ms_boost',)


def validate_arm(arm):
    if arm not in MARGINS:
        raise ValueError('Unknown arm: %s' % arm)
    return arm


def margin_for(arm):
    validate_arm(arm)
    return MARGINS[arm]


def summarize_lateness(latencies):
    return dict(lateness_seconds=stats(latencies), dispatched=len(latencies),
                at_or_over_4ms=sum(v >= GATE for v in latencies),
                over_2ms=sum(v > 0.002 for v in latencies),
                over_3ms=sum(v > 0.003 for v in latencies))


def run_arm(arm, periods, collector):
    margin = margin_for(arm)
    latencies, spins = [], []
    started = time.perf_counter()
    cpu_started = time.thread_time()
    target = started + PERIOD
    while len(latencies) < periods:
        now = time.perf_counter()
        if margin is None:
            if now < target:
                time.sleep(WAIT)
        else:
            spin_start = target - margin
            if now < spin_start:
                time.sleep(min(WAIT, spin_start - now))
            else:
                boost = ThreadPriority(TIME_CRITICAL) if arm in BOOST_ARMS else None
                if boost:
                    boost.__enter__()
                spin_began = time.perf_counter()
                while time.perf_counter() < target:
                    pass
                spins.append(time.perf_counter() - spin_began)
                if boost:
                    boost.__exit__(None, None, None)
        now = time.perf_counter()
        if now >= target:
            latencies.append(now - target)
            target += PERIOD
    wall = time.perf_counter() - started
    cpu = time.thread_time() - cpu_started
    return dict(dispatch=summarize_lateness(latencies), spin_seconds=stats(spins),
                wall_seconds=wall, thread_cpu_seconds=cpu,
                thread_cpu_ratio=cpu / wall if wall else 0.0,
                collector=stats(collector.delays))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--periods', type=int, default=1500)
    parser.add_argument('--arms', default=','.join(MARGINS))
    parser.add_argument('--load-threads', type=int, default=2)
    parser.add_argument('--out', default=None)
    args = parser.parse_args()
    arms = [a.strip() for a in args.arms.split(',') if a.strip()]
    for arm in arms:
        validate_arm(arm)

    loaders = [LoadGenerator() for _ in range(args.load_threads)]
    for loader in loaders:
        loader.start()
    try:
        report = {}
        for arm in arms:
            collector = Collector()
            collector.start()
            report[arm] = run_arm(arm, args.periods, collector)
            collector.stop.set()
            collector.join(timeout=2)
    finally:
        for loader in loaders:
            loader.stop.set()
        for loader in loaders:
            loader.join(timeout=2)

    document = dict(status='PASSED_OFFLINE_SPIN_WAIT', hardware_actions=0,
                    constants=dict(period_seconds=PERIOD, gate_seconds=GATE,
                                   wait_seconds=WAIT, collector_wait_seconds=COLLECTOR_WAIT),
                    sample=dict(periods=args.periods, load_threads=args.load_threads),
                    arms=report)
    text = json.dumps(document, indent=2, sort_keys=True) + '\n'
    if args.out:
        path = pathlib.Path(args.out)
        if not path.is_absolute():
            path = ROOT / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        print('WROTE', path)
    for arm in arms:
        d = report[arm]
        print('%-14s lateness max %7.3f ms  >=4ms %2d  cpu %5.1f%%  spin max %6.3f ms  collector max %6.3f ms'
              % (arm, d['dispatch']['lateness_seconds'].get('maximum', 0) * 1e3,
                 d['dispatch']['at_or_over_4ms'], d['thread_cpu_ratio'] * 100,
                 d['spin_seconds'].get('maximum', 0) * 1e3,
                 d['collector'].get('maximum', 0) * 1e3))


if __name__ == '__main__':
    main()
