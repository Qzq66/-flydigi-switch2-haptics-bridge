"""Process supervision helpers; dependencies are supplied by the caller.

Importing this module does not start processes or load platform libraries.
"""
import subprocess


def communicate_bounded(process, timeout):
    """Kill and reap a timed-out child; preserve the independent parent stop."""
    if timeout <= 0:
        raise ValueError('Positive child timeout required')
    killed = False
    try:
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            killed = True
            process.kill()
            stdout, stderr = process.communicate(timeout=2)
        return stdout, stderr, killed
    finally:
        # Also covers a failed communicate() or a second timeout after kill.
        if process.poll() is None:
            process.kill()
            process.wait(timeout=2)


def child_succeeded(report, exit_code, live=False):
    """A clean OS exit alone is not evidence that a hardware child succeeded."""
    if not isinstance(report, dict) or exit_code != 0:
        return False
    expected = 'PASSED_SWITCH_WIFI_FLYDIGI_LIMITED_LIVE' if live else 'PASSED_PICO_WIFI_FLYDIGI_BENCH'
    return (report.get('status') == expected and
            not any(report.get(k) for k in ('error', 'cleanup_error', 'pico_reset_error')))
