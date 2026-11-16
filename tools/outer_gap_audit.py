"""Deterministic audit of the frozen pre-fault outer gap; pure-host cadence probe.

Reads the frozen 165425 child report (SHA-256 pinned by the caller), attributes the
inter-tick gap with the same clipped-union model as outer_loop_probe, and separately
measures the composed pre-step primitives (cancellation stat, inbox drain, UI enqueue,
sleep 1ms) on this host. No device, network, or hardware entry.
"""
import argparse, collections, ctypes, hashlib, json, pathlib, statistics, tempfile, time
ROOT = pathlib.Path(__file__).absolute().parents[1]
CAMPAIGN = ROOT / 'docs/campaigns/outer-loop-2026-11-15'
GATE = .004


def digest(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def _spans(row):
    pairs = (('drain', row['start'], row['drain_end']), ('enqueue', row['drain_end'], row['enqueue_end']),
             ('entry_to_tick', row['enqueue_end'], row['tick_entry']), ('tick', row['tick_entry'], row['end']))
    out = []
    for phase, a, b in pairs:
        if a is None or b is None:
            raise ValueError('Missing span boundary: ' + phase)
        if a > b:
            raise ValueError('Negative span: ' + phase)
        out.append((phase, a, b))
    return out


def _stats(values):
    if not values:
        raise ValueError('No samples')
    ordered = sorted(values)
    pick = lambda p: ordered[min(len(ordered) - 1, int(p * len(ordered)))]
    return dict(count=len(ordered), minimum=ordered[0], median=statistics.median(ordered),
                p95=pick(.95), p99=pick(.99), maximum=ordered[-1])


def audit(child, source):
    io = child['dispatch_io']
    ff = io['first_fault']
    ctx = [dict(row) for row in ff['context']]
    if len(ctx) < 2 or ff['tick_entry'] is None or ff['target'] is None:
        raise ValueError('Fault tick entry/target not recorded')
    for a, b in zip(ctx, ctx[1:]):
        if b['start'] <= a['start']:
            raise ValueError('Step rows not increasing')
        if max(end for _, _, end in _spans(a)) > b['start']:
            raise ValueError('Step rows overlap at ' + str(b['step']))
    gaps = []
    for a, b in zip(ctx, ctx[1:]):
        start, end = a['end'], b['start']
        covered = sum(max(0., min(end, e) - max(start, s)) for _, s, e in _spans(a) + _spans(b))
        if covered > 1e-9:
            raise ValueError('Measured span crosses the inter-step gap')
        gaps.append(dict(after_step=a['step'], before_step=b['step'], seconds=end - start,
                         covered_seconds=covered, unattributed_seconds=end - start - covered))
    entry_delay = ff['tick_entry'] - ctx[-1]['start']
    fault_gap = gaps[-1]['seconds']
    margins = [row['target'] - row['end'] for row in ctx[:-1]
               if row['target'] is not None and row['target'] - row['end'] >= 0]
    if not margins:
        raise ValueError('No dispatch margin in context')
    thresholds = [margin + GATE for margin in margins]
    lateness = list(child['output_lateness_seconds'])
    checks = dict(fault_lateness_matches_recorded=abs(ff['tick_entry'] - ff['target'] - ff['lateness_seconds']) <= 1e-9,
                  gap_plus_entry_delay_matches=abs(ff['tick_entry'] - ctx[-2]['end'] - (fault_gap + entry_delay)) <= 1e-9,
                  gap_entirely_outside_measured_spans=(fault_gap - entry_delay) / fault_gap > .999,
                  no_dispatch_exceeded_gate=all(value <= GATE for value in lateness),
                  no_automatic_recovery=child.get('automatic_fault_recovery') is not True,
                  drain_is_not_source_ingestion=io.get('source_ingestion_profiled') is False)
    return dict(source=source, fault=ff['fault'], frames=child['output_frames'],
                active_steps_before_fault=ctx[-1]['step'], steps_total=io['steps'],
                gap_seconds=fault_gap, fault_lateness_seconds=ff['lateness_seconds'],
                entry_delay_seconds=entry_delay,
                unmeasured_in_gap_seconds=fault_gap - entry_delay,
                measured_share_of_gap=entry_delay / fault_gap,
                gaps=_stats([gap['seconds'] for gap in gaps]),
                step_periods=_stats([b['start'] - a['start'] for a, b in zip(ctx, ctx[1:])]),
                margins=_stats(margins), thresholds=_stats(thresholds),
                fault_gap_exceeds_largest_local_threshold=fault_gap > max(thresholds),
                steps_ended_after_target=sum(1 for row in ctx[:-1] if row['target'] is not None and row['end'] > row['target']),
                lateness=_stats(lateness),
                checks=checks,
                attribution_scope=dict(
                    measured=['drain', 'enqueue', 'entry_to_tick', 'tick'],
                    not_measured=['cancellation stat', 'core-side inbox drain', 'fault check',
                                  'publish enqueue cost before step', 'loop overhead', 'wakeup delay'],
                    note='Rows and gaps are disjoint, so the gap is entirely outside measured spans. '
                         'This bounds measurement coverage; it does not name the source.'),
                status='PASSED_DETERMINISTIC_FROZEN_AUDIT' if all(checks.values()) else 'INCOMPLETE')


class _Timer:
    def __init__(self, request):
        self.requested = request
        self.winmm = None
        self.request = self.release = None

    def __enter__(self):
        if self.requested:
            self.winmm = ctypes.WinDLL('winmm')
            self.request = self.winmm.timeBeginPeriod(1)
        return self

    def __exit__(self, *exc):
        if self.winmm is not None:
            self.release = self.winmm.timeEndPeriod(1)
        return False


def _run_arm(iterations):
    with tempfile.TemporaryDirectory(prefix='outer-gap-host-') as tmp:
        tmp = pathlib.Path(tmp)
        cancel = tmp / 'arm.cancel'
        cancel.write_text('{}', encoding='utf-8')
        phase = tmp / 'phase.json'
        pending = phase.with_name('.phase.json.pending')
        payload = json.dumps(dict(phase='INPUT_READY', clock='monotonic', deadline_monotonic=1.,
                                  pad='x' * 1024), indent=1)
        inbox = collections.deque(maxlen=8)
        periods, work = [], []
        for i in range(iterations):
            start = time.perf_counter()
            cancel.exists()
            while inbox:
                inbox.popleft()
            inbox.append(i)
            if i % 200 == 0:
                pending.write_text(payload, encoding='utf-8')
                pending.replace(phase)
            drained = time.perf_counter()
            time.sleep(.001)
            periods.append(time.perf_counter() - start)
            work.append(drained - start)
    return periods, work


def _resolution():
    ntdll = ctypes.WinDLL('ntdll')
    minimum, current, maximum = ctypes.c_ulong(), ctypes.c_ulong(), ctypes.c_ulong()
    status = ntdll.NtQueryTimerResolution(ctypes.byref(minimum), ctypes.byref(current), ctypes.byref(maximum))
    return dict(status=status, minimum_100ns=minimum.value, current_100ns=current.value,
                maximum_100ns=maximum.value)


def host_probe(iterations):
    start = time.perf_counter()
    time.sleep(.001)
    if time.perf_counter() <= start:
        raise RuntimeError('Counters do not advance')
    before = _resolution()
    arms = {}
    for name, requested in (('timer_1ms', True), ('timer_unrequested', False)):
        with _Timer(requested) as timer:
            periods, work = _run_arm(iterations)
        arms[name] = dict(iterations=iterations, timer_request=timer.request,
                          timer_release=timer.release, sleep_request_seconds=.001,
                          phase_write_every=200,
                          period_seconds=_stats(periods), work_seconds=_stats(work),
                          periods_over_4ms=sum(value > .004 for value in periods),
                          periods_over_6ms=sum(value > .006 for value in periods),
                          periods_over_8p7ms=sum(value > .0087 for value in periods))
    return dict(scope='Pure-host composed primitives; no device, network or hardware entry',
                process='single process, single loop, phase file replaced every 200 iterations',
                resolution_before=before, resolution_after=_resolution(),
                resolution_note=('The unrequested arm is only a default-resolution control when '
                                 'resolution_before.current_100ns >= 156250; another process '
                                 'holding a finer resolution poisons it.'),
                elapsed_seconds=time.perf_counter() - start, arms=arms)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frozen', type=pathlib.Path, required=True)
    parser.add_argument('--expect-sha256')
    parser.add_argument('--host-iterations', type=int, default=0)
    args = parser.parse_args()
    raw = args.frozen.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    if args.expect_sha256 and sha != args.expect_sha256:
        raise ValueError('Frozen report hash mismatch')
    try:
        shown = str(args.frozen.resolve().relative_to(ROOT)).replace('\\', '/')
    except ValueError:
        shown = str(args.frozen)
    report = dict(status='COMPLETED', hardware_actions=0, network_actions=0,
                  product_acceptance='INCOMPLETE (unchanged)', root_cause='unproven',
                  frozen=dict(path=shown, sha256=sha),
                  audit=audit(json.loads(raw)['child'], shown))
    if args.host_iterations:
        report['host'] = host_probe(args.host_iterations)
    CAMPAIGN.mkdir(parents=True, exist_ok=True)
    out = CAMPAIGN / ('outer-gap-audit-' + time.strftime('%Y%m%d-%H%M%S') + '.json')
    if out.exists():
        raise ValueError('Evidence output exists; refusing overwrite')
    out.write_text(json.dumps(report, indent=2), encoding='utf-8')
    a = report['audit']
    print(a['status'], 'gap_ms=%.4f unmeasured_ms=%.4f' % (a['gap_seconds'] * 1000,
                                                           a['unmeasured_in_gap_seconds'] * 1000))
    for name, arm in report.get('host', {}).get('arms', {}).items():
        print(name, 'period_median_ms=%.3f period_max_ms=%.3f over4=%d over8.7=%d' % (
            arm['period_seconds']['median'] * 1000, arm['period_seconds']['maximum'] * 1000,
            arm['periods_over_4ms'], arm['periods_over_8p7ms']))
    print(out)
    return 0 if a['status'] == 'PASSED_DETERMINISTIC_FROZEN_AUDIT' else 1


if __name__ == '__main__':
    raise SystemExit(main())
