"""Decompose the frozen sustained-trial step budget (offline; no device, no network).

The product scheduler keeps a fixed 8 ms target grid and faults when `start - target > 4 ms`
(`Game PCM scheduler late; no catch-up`).  For each dispatched frame the frozen report
already records two of the three budget terms: the dispatch lateness and the dispatch work
(`output_lateness_seconds`, `output_write_seconds`).  This tool reports the implied
remaining margin, and decomposes the recorded fault frame into: lateness already spent,
distance from the last loop check to the pending deadline, and wake delay.
"""
import argparse, hashlib, json, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
CAMPAIGN = ROOT / 'docs/campaigns/outer-loop-2026-11-15'
GATE = .004
PERIOD = .008


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _stats(values):
    s = sorted(values)
    if not s:
        raise ValueError('No samples')
    pick = lambda f: s[min(len(s) - 1, int(round(f * (len(s) - 1))))]
    return dict(count=len(s), minimum=s[0], median=pick(.5), p95=pick(.95),
                p99=pick(.99), maximum=s[-1])


def fault_decomposition(rows, gate=GATE):
    """Explain the fault frame from the step context that precedes it."""
    if len(rows) < 3:
        raise ValueError('Fault context too short')
    previous, last = rows[-2], rows[-1]
    deadline = last['target']
    last_check = previous['start']
    wake = last['start'] - last_check
    return dict(last_check_to_deadline=deadline - last_check,
                wake_delay=wake,
                wake_delay_allowance=deadline - last_check + gate,
                observed_lateness=last['tick_entry'] - deadline,
                exceeded_allowance=wake - (deadline - last_check + gate),
                previous_lateness=previous['tick_entry'] - previous['target'])


def model(child):
    late = list(child['output_lateness_seconds'])
    write = list(child['output_write_seconds'])
    if len(late) != len(write):
        raise ValueError('Lateness and write series differ in length')
    margin = [GATE - value for value in late]
    return dict(status='COMPLETED', hardware_actions=0, network_actions=0,
                gate_seconds=GATE, period_seconds=PERIOD, dispatch_frames=len(late),
                lateness=_stats(late), work=_stats(write), gate_margin=_stats(margin),
                frames_over_2ms_late=sum(1 for value in late if value > .002))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frozen', type=pathlib.Path, required=True)
    parser.add_argument('--expect-sha256')
    parser.add_argument('--output', type=pathlib.Path)
    args = parser.parse_args()
    raw = args.frozen.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    if args.expect_sha256 and sha != args.expect_sha256:
        raise ValueError('Frozen report hash mismatch')
    child = json.loads(raw)['child']
    rows = child['dispatch_io']['first_fault']['context']
    report = model(child)
    report['frozen'] = dict(path=str(args.frozen), sha256=sha)
    report['fault'] = fault_decomposition(rows)
    report['fault']['recorded_fault_lateness'] = child['dispatch_io']['first_fault']['lateness_seconds']
    out = args.output or CAMPAIGN / ('step-budget-' + __import__('time').strftime('%Y%m%d-%H%M%S') + '.json')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding='utf-8')
    f, m = report['fault'], report['gate_margin']
    print('frames=%d lateness median=%.3fms max=%.3fms; gate margin median=%.3fms min=%.3fms' % (
        report['dispatch_frames'], report['lateness']['median'] * 1e3,
        report['lateness']['maximum'] * 1e3, m['median'] * 1e3, m['minimum'] * 1e3))
    print('fault: last check -> deadline %.3fms, wake delay %.3fms, allowance %.3fms, lateness %.3fms' % (
        f['last_check_to_deadline'] * 1e3, f['wake_delay'] * 1e3,
        f['wake_delay_allowance'] * 1e3, f['observed_lateness'] * 1e3))
    print(out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
