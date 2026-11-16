"""Offline verification of the bounded priority window integration (no hardware).

Three claims are checked, in order:
  A. synthetic: the boost is held exactly across the action and always released,
     including when the action raises;
  B. real kernel: the same holds on a real thread (priority read back after each arm),
     and the enabled window keeps wake overshoot under 3 ms over 4 000 armed steps;
  C. integration: the window is short (a boost left on during I/O would be a bug).
"""
import ctypes, json, pathlib, sys, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from thread_priority import kernel32, NORMAL, TIME_CRITICAL
from priority_window import PriorityWindow

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / 'docs' / 'campaigns' / 'outer-loop-2026-11-15'
ITERATIONS = 4000


def stats(values):
    values = sorted(values)
    n = len(values) or 1
    return {'n': len(values), 'min': values[0] if values else None,
            'median': values[n // 2] if values else None,
            'p99': values[min(n - 1, int(n * 0.99))] if values else None,
            'max': values[-1] if values else None,
            'over_3ms': sum(1 for v in values if v > 3.0),
            'over_5ms': sum(1 for v in values if v > 5.0)}


class FakeKernel:
    def __init__(self):
        self.current = NORMAL
        self.levels = []

    def GetCurrentThread(self):
        return 1

    def GetThreadPriority(self, thread):
        return self.current

    def SetThreadPriority(self, thread, level):
        self.levels.append(level)
        self.current = level
        return True


def synthetic_checks():
    results = {}
    seen = []

    def boost_factory(kernel):
        from thread_priority import ThreadPriority
        return lambda: ThreadPriority(TIME_CRITICAL, kernel=kernel)

    kernel = FakeKernel()
    window = PriorityWindow(boost_factory=boost_factory(kernel))
    window.step(lambda: seen.append(kernel.current))
    results['held_during_action'] = seen == [TIME_CRITICAL]
    results['restored_after_action'] = kernel.current == NORMAL

    kernel2 = FakeKernel()
    window2 = PriorityWindow(boost_factory=boost_factory(kernel2))
    raised = False
    try:
        window2.step(lambda: (_ for _ in ()).throw(RuntimeError('late frame')))
    except RuntimeError:
        raised = True
    results['exception_propagates'] = raised
    results['restored_after_exception'] = kernel2.current == NORMAL

    kernel3 = FakeKernel()
    window3 = PriorityWindow(enabled=False, boost_factory=boost_factory(kernel3))
    window3.step(lambda: None)
    results['disabled_makes_no_call'] = kernel3.levels == []
    return results


def arm(iterations, marker, phase_path, enabled):
    window = PriorityWindow(enabled=enabled)
    overshoots, holds = [], []
    for index in range(iterations):
        def action():
            marker.exists()
            if index % 200 == 0:
                phase_path.write_text('{"phase":"armed","clock":"monotonic"}', encoding='utf-8')
            requested = time.perf_counter() + 0.001
            time.sleep(0.001)
            overshoots.append((time.perf_counter() - requested) * 1000.0)
        window.step(action)
        holds.append(window.last_hold_ms)
    return window, overshoots, holds


def current_priority(kernel):
    return kernel.GetThreadPriority(kernel.GetCurrentThread())


def main():
    stamp = time.strftime('%Y%m%d-%H%M%S')
    OUT.mkdir(parents=True, exist_ok=True)
    marker = OUT / 'priority-window.marker'
    phase = OUT / 'priority-window.phase.json'
    marker.write_text('armed', encoding='utf-8')
    kernel = kernel32()
    original = current_priority(kernel)

    synthetic = synthetic_checks()

    off_window, off_overshoots, off_holds = arm(ITERATIONS, marker, phase, enabled=False)
    after_off = current_priority(kernel)

    on_window, on_overshoots, on_holds = arm(ITERATIONS, marker, phase, enabled=True)
    after_on = current_priority(kernel)

    fault_raised = False
    try:
        PriorityWindow().step(lambda: (_ for _ in ()).throw(RuntimeError('fault frame')))
    except RuntimeError:
        fault_raised = True

    checks = dict(synthetic)
    checks['real_original_priority'] = original == NORMAL
    checks['real_restored_after_disabled_arm'] = after_off == original
    checks['real_restored_after_enabled_arm'] = after_on == original
    checks['real_restored_after_fault'] = fault_raised and current_priority(kernel) == original
    checks['enabled_max_overshoot_under_3ms'] = stats(on_overshoots)['max'] < 3.0
    checks['window_is_short'] = max(on_holds) < 50.0
    checks['boost_actually_applied'] = on_window.steps == ITERATIONS and on_window.max_hold_ms > 0

    status = 'PASSED_PRIORITY_WINDOW_OFFLINE' if all(checks.values()) else 'INCOMPLETE'
    document = {
        'status': status,
        'scope': 'Offline priority-window integration check; no hardware opened, no protocol value changed',
        'iterations': ITERATIONS,
        'checks': checks,
        'priority': {'original': original, 'time_critical': TIME_CRITICAL},
        'arms': {
            'window_disabled': {'overshoot_ms': stats(off_overshoots),
                                'holds_ms': stats(off_holds)},
            'window_enabled': {'overshoot_ms': stats(on_overshoots),
                               'holds_ms': stats(on_holds)},
        },
        'evidence_tool': 'tools/verify_priority_window.py',
    }
    path = OUT / ('priority-window-%s.json' % stamp)
    path.write_text(json.dumps(document, indent=2), encoding='utf-8')
    print(status)
    for name, value in checks.items():
        print('  %-36s %s' % (name, 'PASS' if value else 'FAIL'))
    print('  enabled overshoot ms:', document['arms']['window_enabled']['overshoot_ms'])
    print('  disabled overshoot ms:', document['arms']['window_disabled']['overshoot_ms'])
    print(path)
    return 0 if status.startswith('PASSED') else 1


if __name__ == '__main__':
    raise SystemExit(main())
