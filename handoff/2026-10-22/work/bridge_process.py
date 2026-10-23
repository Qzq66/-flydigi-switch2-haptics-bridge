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

def input_end_check_succeeded(report,exit_code):
    """Input-only real-host check requires terminal confirmation and sampled input."""
    if not isinstance(report,dict) or exit_code!=0:return False
    relay=report.get('input_relay')
    if not isinstance(relay,dict) or type(relay.get('nonneutral_reads')) is not int or relay['nonneutral_reads']<=0:return False
    return (report.get('status')=='PASSED_SWITCH_WIFI_INPUT_END_CHECK' and
        report.get('ended_reason')=='terminal stream complete' and
        all(report.get(k) is True for k in ('terminal_received','terminal_ack_replied','collector_ended','timer_released')) and
        report.get('motor_output_enabled') is False and report.get('output_frames')==0 and
        not any(report.get(k) for k in ('error','cleanup_error','pico_reset_error','output_fault')))


def game_end_check_succeeded(report,exit_code):
    """Program completion only: registration prompts do not prove game haptics."""
    if not isinstance(report,dict) or exit_code!=0:return False
    if report.get('staged_game'):
        if report.get('pre_arm_output_frames')!=0 or report.get('pre_arm_prompt_counts')!=[0,0]:return False
        if not isinstance(report.get('armed_at_pc_clock'),(int,float)) or report['armed_at_pc_clock']<=0:return False
    counts=report.get('prompt_counts');samples=report.get('active_samples')
    if not isinstance(counts,list) or len(counts)!=2:return False
    if not all(type(n) is int and 0<=n<=3 for n in counts) or not any(counts):return False
    if samples!=[120*n for n in counts]:return False
    return (report.get('status')=='PASSED_SWITCH_WIFI_GAME_PILOT_PROGRAM_CHECKS' and
        report.get('ended_reason')=='terminal stream complete' and
        all(report.get(k) is True for k in ('terminal_received','terminal_ack_replied','collector_ended','timer_released','runtime_disable_ack','motor_output_enabled')) and
        type(report.get('output_frames')) is int and report['output_frames']>0 and
        type(report.get('maximum_offset')) is int and 0<report['maximum_offset']<=12 and
        not any(report.get(k) for k in ('error','cleanup_error','pico_reset_error','output_fault')))
