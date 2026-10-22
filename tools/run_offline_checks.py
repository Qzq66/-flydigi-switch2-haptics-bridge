#!/usr/bin/env python3
"""Pure-data checks with network/ctypes/process guards, never hardware owners.

The guard is an accidental-I/O tripwire, not a sandbox for arbitrary code.
"""
import argparse
import hashlib
import json
import pathlib
import platform
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
WORK = ROOT / 'handoff/2026-10-22/work'
TESTS = [
    'test-switch-hd-decode.py', 'test-bridge-runtime.py',
    'test-bridge-prompt.py', 'test-bridge-input.py',
    'test-pico-continuous-format.py', 'test-pico-capture-format.py',
    'test-bridge-game-pilot.py', 'test-bridge-end.py',
    'test-bridge-capture-replay.py', 'test-bridge-platform.py', 'test-capture-corpus.py', 'test-bridge-adapters.py',
]
BOOTSTRAP = '''
import runpy, sys
def deny_hardware(event, args):
    if event.startswith('socket.') or event in ('ctypes.dlopen', 'subprocess.Popen', 'os.system'):
        raise RuntimeError('Offline test blocked hardware/process operation: ' + event)
    if event == 'import' and args[0] in ('xinput_readonly', 'hid', 'hidapi'):
        raise RuntimeError('Offline test blocked hardware module: ' + args[0])
sys.addaudithook(deny_hardware)
sys.path.insert(0, sys.argv[1])
runpy.run_path(sys.argv[2], run_name='__main__')
'''


def run_checks():
    results = []
    for name in TESTS:
        result = dict(script=name, passed=False)
        try:
            run = subprocess.run(
                [sys.executable, '-c', BOOTSTRAP, str(WORK), str(WORK / name)],
                cwd=WORK.parent, capture_output=True, text=True, encoding='utf-8', timeout=30)
            if run.returncode:
                result['error'] = (run.stderr or run.stdout)[-3000:]
            else:
                try:
                    checks = json.loads(run.stdout)
                    if not isinstance(checks, list) or not checks or not all(
                            isinstance(c, dict) and c.get('passed') is True for c in checks):
                        raise ValueError('Test output must contain passing named checks')
                    result.update(passed=True, checks=len(checks), details=checks)
                except json.JSONDecodeError:
                    legacy = re.fullmatch(r'(\d+) capture format checks passed; no devices opened\s*', run.stdout)
                    if name == 'test-pico-capture-format.py' and legacy:
                        result.update(passed=True, checks=int(legacy.group(1)))
                    else:
                        result['error'] = 'Unrecognized test output'
        except (subprocess.TimeoutExpired, OSError, ValueError) as exc:
            result['error'] = str(exc)
        results.append(result)
        print(json.dumps({k: v for k, v in result.items() if k != 'details'}, ensure_ascii=False))
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=pathlib.Path, help='New report path; existing evidence is never overwritten')
    parser.add_argument('--write-report', action='store_true', help='Legacy report path, only if absent')
    args = parser.parse_args()
    if args.report and args.write_report:
        parser.error('Choose --report or --write-report')
    report_path = args.report or (ROOT / 'docs/OFFLINE_EXPORT_VERIFICATION.json' if args.write_report else None)
    if report_path and report_path.exists():
        parser.error('Report already exists; use a new report path to preserve prior evidence')
    results = run_checks()
    if report_path:
        sources = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in sorted(WORK.glob('*.py'))}
        sources['tools/run_offline_checks.py'] = hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest()
        report = dict(platform=sys.platform, python=platform.python_version(),
                      hardware_access=False, io_guard=True, results=results,
                      total_checks=sum(r.get('checks', 0) for r in results), source_sha256=sources,
                      capture_sha256={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                          for pattern in ('pico-continuous-capture-*.json', 'flydigi-live-bench-child-*.json',
                                          'pico-bridge-v042-raw-test-20261022-165112.json')
                          for p in sorted((WORK.parent / 'outputs').glob(pattern))})
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with report_path.open('x', encoding='utf-8') as output:
            json.dump(report, output, ensure_ascii=False, indent=2)
            output.write('\n')
    return 0 if all(r['passed'] for r in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
