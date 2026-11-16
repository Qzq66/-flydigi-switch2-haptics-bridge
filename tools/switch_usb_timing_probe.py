"""Neutral-only USB timing diagnostic for the Switch-mode endpoint.

Sends no motor parameters: every packet is 0x10 with both channels at 00 01 40 40.
The dispatch grid and the transport bound are separate, so this measures how long
Windows takes to complete a neutral WriteFile without tripping the 4 ms schedule.
Manual click required; no configuration, initialization or feature command.
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

FRAMES = 24
DENSE_FRAMES = 32
ASYNC_PERIOD_S = 0.008
ASYNC_FRAMES = 32
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--folder', type=Path, required=True)
    parser.add_argument('--mode', choices=('grid', 'dense', 'async'), default='grid',
                        help='grid: 4 ms grid; dense: back-to-back; async: 8 ms grid, overlapped writes')
    args = parser.parse_args()
    args.folder.mkdir(parents=True, exist_ok=False)
    frames = ASYNC_FRAMES if args.mode == 'async' else (DENSE_FRAMES if args.mode == 'dense' else FRAMES)
    devices = enumerate_usb()
    if len(devices) != 1:
        raise ValueError('Exactly one Switch USB target required')
    device = devices[0]
    metadata = inspect_output_reports(device)
    device['declared_output_ids'] = sorted({x['report_id'] for x in metadata})
    if not any(x['report_id'] == 16 and x.get('bit_size') == 8 and x.get('report_count') == 63
               for x in metadata):
        raise ValueError('Expected 64-byte report 0x10 declaration missing')
    (args.folder / 'device-private.json').write_text(json.dumps(device, indent=2), encoding='utf-8')

    result = dict(status='NOT_STARTED', transport='USB', mode='Switch',
                  scope='neutral-only transport timing; no motor parameters',
                  neutral_only=True, nonzero_output_reports=0,
                  configuration_commands=0, initialization_commands=0, feature_commands=0,
                  pico_access=False, frames_planned=frames, probe_mode=args.mode,
                  transport_timeout_ms=TRANSPORT_TIMEOUT_MS,
                  dispatch_period_ms=timing.PERIOD_S * 1000,
                  max_dispatch_late_ms=timing.MAX_DISPATCH_LATE_S * 1000,
                  output_capabilities=metadata)

    import tkinter as tk
    root = tk.Tk()
    root.title('Switch USB：仅中性包时序诊断')
    root.geometry('720x380')
    root.attributes('-topmost', True)
    label = tk.Label(root, font=('Microsoft YaHei UI', 12), justify='left', wraplength=670,
                     text='保持 Switch 模式；Steam、飞智 Engine、测试网页全部退出。\n'
                          '松开全部按键、摇杆、扳机。点击后倒计时 6 秒。\n'
                          f'本轮只发 {frames} 个中性包（左右均 00014040），不会震动。\n'
                          '用途：把“派发截止”和“USB 传输完成”分开测量。\n'
                          '不写配置、不发初始化/Feature 命令、不操作 Pico。')
    label.pack(padx=20, pady=20)
    cancelled = threading.Event()
    done = threading.Event()
    worker = None
    started = None
    result_at = None
    deadline = time.monotonic() + 90

    def task():
        reader = writer = None
        timer_active = False
        timer = None
        stats = timing.Stats()
        try:
            current = enumerate_usb()
            if len(current) != 1 or current[0]['path'] != device['path']:
                raise RuntimeError('USB_TARGET_CHANGED')
            reader = Reader(device)
            baseline = observe(reader, 10, cancelled.is_set)
            result['pre_input_reports'] = len(baseline)
            require_neutral(baseline)
            timer = ctypes.WinDLL('winmm')
            timer_active = timer.timeBeginPeriod(1) == 0
            if not timer_active:
                raise RuntimeError('TIMER_UNAVAILABLE')
            overlapped = AsyncWriter(Writer(device)) if args.mode == 'async' else None
            writer = overlapped if overlapped is not None else Writer(device)
            period = ASYNC_PERIOD_S if args.mode == 'async' else timing.PERIOD_S
            result['manual_started_at'] = time.monotonic()
            base = time.perf_counter()
            last = base
            prev_done = base
            sent = 0
            max_gap = 0.0
            cadence = []
            for index in range(frames):
                if cancelled.is_set():
                    raise RuntimeError('CANCELLED')
                if args.mode == 'grid' or args.mode == 'async':
                    due = base + index * period
                    while time.perf_counter() < due:
                        time.sleep(max(0., min(.001, due - time.perf_counter())))
                    now = time.perf_counter()
                else:
                    now = due = time.perf_counter()
                packet = report(index & 15)  # both channels neutral by construction
                if packet[2:10] != NEUTRAL + NEUTRAL:
                    raise RuntimeError('NON_NEUTRAL_PACKET_BLOCKED')
                submit = time.perf_counter()
                if overlapped is not None:
                    overlapped.submit(packet)
                    done_at = time.perf_counter()
                else:
                    writer.send(packet, timeout_ms=TRANSPORT_TIMEOUT_MS)
                    done_at = time.perf_counter()
                elapsed = done_at - submit
                # Neutral-only run: a late slot is recorded, never a stop condition.
                outcome = timing.classify(due=due, now=now, io_elapsed=elapsed)
                stats.add(outcome['late_ms'], outcome['io_ms'])
                cadence.append((done_at - prev_done) * 1000)
                prev_done = done_at
                sent += 1
                max_gap = max(max_gap, now - last)
                last = now
            result['frames_sent'] = sent
            result['timing'] = stats.summary()
            result['completion_cadence_ms'] = {
                'min': round(min(cadence), 4),
                'median': round(sorted(cadence)[len(cadence) // 2], 4),
                'max': round(max(cadence), 4),
            }
            result['max_gap_ms'] = max_gap * 1000
            if overlapped is not None:
                drained_async = overlapped.wait_idle(2.0)
                result['async_writer'] = overlapped.summary()
                result['async_idle'] = drained_async
            writer.close()
            writer = None
            drained = 0
            while drained < 128:
                if reader.poll() is None:
                    break
                drained += 1
            if drained == 128:
                raise RuntimeError('INPUT_QUEUE_NOT_DRAINED')
            result['post_input_reports'] = len(observe(reader, 10, cancelled.is_set))
            result['status'] = 'NEUTRAL_TIMING_CAPTURED'
        except Exception as exc:
            result['error'] = str(exc)
            result['status'] = 'STOPPED_ON_FAULT'
        finally:
            if writer:
                writer.close()
            if reader:
                reader.close()
            if timer_active:
                result['timer_released'] = timer.timeEndPeriod(1) == 0
            (args.folder / 'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
            done.set()

    def start():
        nonlocal started
        button.config(state='disabled')
        started = time.monotonic() + 6
        result['manual_started'] = True

    def cancel():
        cancelled.set()
        if worker is None:
            (args.folder / 'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
            root.destroy()

    button = tk.Button(root, text='开始中性包时序诊断（6秒准备）', command=start,
                       font=('Microsoft YaHei UI', 12))
    button.pack(pady=6)
    tk.Button(root, text='取消／停止', command=cancel).pack(pady=6)
    root.protocol('WM_DELETE_WINDOW', cancel)

    def poll():
        nonlocal worker, result_at
        now = time.monotonic()
        if now >= deadline:
            cancel()
        if cancelled.is_set() and worker is None:
            return
        if started is not None and worker is None and not cancelled.is_set():
            if now < started:
                label.config(text='约%d 秒后开始。保持全松。' % (started - now + 1))
            else:
                label.config(text='正在发送 24 个中性包并测量传输时间…')
                worker = threading.Thread(target=task, daemon=False)
                worker.start()
        if done.is_set():
            if result_at is None:
                result_at = now
                label.config(text='本轮结束：%s\n（中性包，不应有震动）' % result['status'])
            if cancelled.is_set() or now - result_at > 6:
                root.destroy()
                return
        root.after(30, poll)

    root.after(100, root.lift)
    root.after(30, poll)
    print('SWITCH_USB_TIMING_WINDOW_READY', flush=True)
    root.mainloop()
    if worker:
        worker.join()
    print(result['status'], flush=True)


if __name__ == '__main__':
    main()
