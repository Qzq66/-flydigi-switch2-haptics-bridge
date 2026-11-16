"""Send reviewed 0x10 haptic frames through the overlapped writer.

Frames are the reviewed low-strength packets from switch_rumble_packet (only
NEUTRAL or LOW_160 per channel, validated), dispatched on the measured 8 ms grid
with the write overlapped in a worker thread. Patterns: segments (left, right,
both, neutral) or compare (left/right twice, for asymmetry checks).
No configuration, initialization or feature command; no Pico access.
Requires --authorize-haptic because this drives the motors.
"""
import argparse
import ctypes
import json
from pathlib import Path
import threading
import time

from switch_usb_readonly import enumerate_usb, Reader
from switch_usb_output import Writer, inspect_output_reports
from switch_usb_async_writer import AsyncWriter
from switch_report30 import decode, require_neutral
from switch_rumble_packet import report, NEUTRAL
import switch_usb_timing as timing

PERIOD_S = 0.008
SEGMENT_FRAMES = 50
COMPARE_FRAMES = 75
TAIL_FRAMES = 12
TRANSPORT_TIMEOUT_MS = 50


def observe(reader, count, cancelled):
    until = time.monotonic() + 1
    packets = []
    while len(packets) < count and time.monotonic() < until:
        if cancelled():
            raise RuntimeError('CANCELLED')
        packet = reader.poll()
        if packet:
            packets.append(decode(packet))
        else:
            time.sleep(.001)
    if len(packets) != count:
        raise RuntimeError('INPUT_LIVENESS_MISSING')
    return packets


def plan(name='segments'):
    frames = []
    if name == 'compare':
        sides = ('left', 'right', 'left', 'right')
        for side in sides:
            for _ in range(COMPARE_FRAMES):
                frames.append((side, report(len(frames) & 15, left=side == 'left',
                                            right=side == 'right')))
    else:
        for side in ('left', 'right', 'both'):
            for _ in range(SEGMENT_FRAMES):
                frames.append((side, report(len(frames) & 15, left=side in ('left', 'both'),
                                            right=side in ('right', 'both'))))
    for _ in range(TAIL_FRAMES):
        frames.append(('neutral', report(len(frames) & 15)))
    return frames


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--folder', type=Path, required=True)
    parser.add_argument('--authorize-haptic', action='store_true')
    parser.add_argument('--pattern', choices=('segments', 'compare'), default='segments')
    args = parser.parse_args()
    if not args.authorize_haptic:
        raise SystemExit('Haptic output is not authorized; pass --authorize-haptic')
    frames = plan(args.pattern)
    args.folder.mkdir(parents=True, exist_ok=False)
    devices = enumerate_usb()
    if len(devices) != 1:
        raise ValueError('Exactly one Switch USB target required')
    device = devices[0]
    metadata = inspect_output_reports(device)
    device['declared_output_ids'] = sorted({item['report_id'] for item in metadata})
    if 0x10 not in device['declared_output_ids']:
        raise ValueError('Expected report 0x10 in the current HID descriptor')
    (args.folder / 'device-private.json').write_text(json.dumps(device, indent=2), encoding='utf-8')

    result = dict(status='NOT_STARTED', transport='USB', mode='Switch',
                  scope='reviewed low-strength haptic frames; overlapped 8 ms grid',
                  pattern='left/right/both 400ms each, then neutral' if args.pattern == 'segments'
                          else 'left 600ms, right 600ms, twice, then neutral',
                  frames_planned=len(frames), period_ms=PERIOD_S * 1000,
                  transport_timeout_ms=TRANSPORT_TIMEOUT_MS,
                  configuration_commands=0, initialization_commands=0,
                  feature_commands=0, pico_access=False,
                  declared_output_ids=device['declared_output_ids'])

    import tkinter as tk
    root = tk.Tk()
    root.title('Switch USB：震动输出联调')
    root.geometry('720x400')
    root.attributes('-topmost', True)
    order = ('左 0.4 秒 → 右 0.4 秒 → 两侧 0.4 秒 → 停' if args.pattern == 'segments'
             else '左 0.6 秒 → 右 0.6 秒 → 再来一遍 → 停')
    tk.Label(root, font=('Microsoft YaHei UI', 12), justify='left', wraplength=670,
             text='保持 Switch 模式并停在桌面；Steam、飞智 Engine 全部退出。\n'
                  '握稳手柄，全松按键、摇杆、扳机。点击后倒计时 6 秒。\n'
                  f'顺序：{order}\n'
                  '只发已审阅的低强度帧；结束后自动归零。').pack(padx=20, pady=20)
    cancelled = threading.Event()
    done = threading.Event()
    deadline = time.monotonic() + 90

    def task():
        reader = overlapped = None
        timer_active = False
        timer = None
        lateness = []
        try:
            current = enumerate_usb()
            if len(current) != 1 or current[0]['path'] != device['path']:
                raise RuntimeError('USB_TARGET_CHANGED')
            reader = Reader(device)
            result['pre_input_reports'] = len(observe(reader, 10, cancelled.is_set))
            require_neutral(observe(reader, 10, cancelled.is_set))
            timer = ctypes.WinDLL('winmm')
            timer_active = timer.timeBeginPeriod(1) == 0
            if not timer_active:
                raise RuntimeError('TIMER_UNAVAILABLE')
            overlapped = AsyncWriter(Writer(device), timeout_ms=TRANSPORT_TIMEOUT_MS)
            result['manual_started_at'] = time.monotonic()
            base = time.perf_counter()
            sent = 0
            for index, (label, packet) in enumerate(frames):
                if cancelled.is_set():
                    raise RuntimeError('CANCELLED')
                due = base + index * PERIOD_S
                while time.perf_counter() < due:
                    time.sleep(max(0., min(.001, due - time.perf_counter())))
                now = time.perf_counter()
                overlapped.submit(packet)
                lateness.append((now - due) * 1000)
                sent += 1
            result['frames_sent'] = sent
            result['idle'] = overlapped.wait_idle(3.0)
            result['writer'] = overlapped.summary()
            result['dispatch_lateness_ms'] = {
                'min': round(min(lateness), 4),
                'median': round(sorted(lateness)[len(lateness) // 2], 4),
                'max': round(max(lateness), 4)}
            overlapped.close()
            overlapped = None
            drained = 0
            while drained < 128:
                if reader.poll() is None:
                    break
                drained += 1
            result['post_input_reports'] = len(observe(reader, 10, cancelled.is_set))
            if result['writer']['written'] != sent or result['writer']['failed']:
                raise RuntimeError('WRITER_INCOMPLETE')
            result['status'] = 'HAPTIC_FRAMES_SENT'
        except Exception as exc:
            result['error'] = str(exc)
            result['status'] = 'STOPPED_ON_FAULT'
        finally:
            try:
                if overlapped is not None:
                    for _ in range(3):
                        overlapped.submit(report(0))
                    overlapped.wait_idle(1.0)
                    overlapped.close()
            except Exception:
                pass
            if reader:
                reader.close()
            if timer_active:
                result['timer_released'] = timer.timeEndPeriod(1) == 0
            (args.folder / 'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
            done.set()

    def start():
        button.config(state='disabled')
        result['manual_started'] = True
        window.after(6000, lambda: threading.Thread(target=task, daemon=True).start())

    def cancel():
        cancelled.set()

    button = tk.Button(root, text='开始震动输出联调（6秒准备）', command=start,
                       font=('Microsoft YaHei UI', 12))
    button.pack(pady=6)
    tk.Button(root, text='取消／停止', command=cancel).pack(pady=6)
    root.protocol('WM_DELETE_WINDOW', cancel)

    def poll():
        if time.monotonic() >= deadline or done.is_set():
            try:
                root.destroy()
            except Exception:
                pass
            return
        root.after(100, poll)

    window = root
    root.after(100, poll)
    root.mainloop()


if __name__ == '__main__':
    main()
