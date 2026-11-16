"""Single bounded Switch pulse policy; injected transport/clock for offline checks."""
import time
from switch_rumble_packet import report

PERIOD = .004
MAX_LATE = .004
MAX_GAP = .080
DURATION = .120


def run(send, cancelled=lambda: False, clock=time.perf_counter, sleep=time.sleep):
    result = dict(status='INCOMPLETE', active_frames=0, stop_write_completed=False,
                  max_dispatch_late_ms=0., max_io_ms=0., max_gap_ms=0.,
                  controller_ack_available=False)
    sequence = 0
    active_attempted = False

    def write(left=False, right=False):
        nonlocal sequence
        start = clock()
        send(report(sequence, left, right))
        sequence = (sequence+1) & 15
        elapsed = clock()-start
        result['max_io_ms'] = max(result['max_io_ms'], elapsed*1000)
        if elapsed > PERIOD:
            raise RuntimeError('IO_EXCEEDED_4MS')

    try:
        write()  # First prove that neutral completes within the existing dispatch budget.
        result['initial_neutral_completed'] = True
        base = clock(); last = base
        for index in range(30):
            due = base+index*PERIOD
            while clock() < due:
                if cancelled(): raise RuntimeError('CANCELLED')
                sleep(max(0., min(.001, due-clock())))
            now = clock()
            if cancelled(): raise RuntimeError('CANCELLED')
            late, gap = now-due, now-last
            result['max_dispatch_late_ms'] = max(result['max_dispatch_late_ms'], late*1000)
            result['max_gap_ms'] = max(result['max_gap_ms'], gap*1000)
            if late > MAX_LATE: raise RuntimeError('DISPATCH_EXCEEDED_4MS')
            if gap > MAX_GAP: raise RuntimeError('GAP_EXCEEDED_80MS')
            if now-base >= DURATION: raise RuntimeError('PULSE_WINDOW_EXPIRED')
            active_attempted = True
            write(True, True)
            result['active_frames'] += 1
            last = now
        while clock() < base+DURATION:
            if cancelled(): raise RuntimeError('CANCELLED')
            sleep(max(0., min(.001, base+DURATION-clock())))
        result['status'] = 'PULSE_SENT'
    except Exception as exc:
        result['error'] = str(exc)
        result['status'] = 'STOPPED_ON_FAULT'
    finally:
        if active_attempted:
            try:
                send(report(sequence))  # One neutral cleanup attempt; never replay active output.
                result['stop_write_completed'] = True
            except Exception as exc:
                result['stop_error'] = str(exc)
                result['status'] = 'STOP_WRITE_FAILED'
        else:
            result['stop_write_completed'] = result.get('initial_neutral_completed', False)
    return result
