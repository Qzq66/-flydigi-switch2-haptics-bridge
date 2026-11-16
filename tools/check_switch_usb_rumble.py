"""Manually gated one-pulse USB Switch test. Report 0x10 only, no setup commands."""
import argparse
import ctypes
import json
from pathlib import Path
import threading
import time
from switch_usb_readonly import enumerate_usb, Reader
from switch_usb_output import Writer, inspect_output_reports
from switch_report30 import decode, require_neutral
from switch_rumble_trial import run


def observe(reader, count, cancelled):
    until = time.monotonic()+1
    packets = []
    while len(packets) < count and time.monotonic() < until:
        if cancelled(): raise RuntimeError('CANCELLED')
        packet = reader.poll()
        if packet:
            packets.append(decode(packet))
        else: time.sleep(.001)
    if len(packets) != count: raise RuntimeError('INPUT_LIVENESS_MISSING')
    return packets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--folder', type=Path, required=True)
    args = parser.parse_args(); args.folder.mkdir(parents=True, exist_ok=False)
    devices = enumerate_usb()
    if len(devices) != 1: raise ValueError('Exactly one Switch USB target required')
    device = devices[0]
    metadata = inspect_output_reports(device)
    device['declared_output_ids'] = sorted({x['report_id'] for x in metadata})
    if not any(x['report_id'] == 16 and x.get('bit_size') == 8 and x.get('report_count') == 63 for x in metadata):
        raise ValueError('Expected 64-byte rumble report declaration missing')
    (args.folder/'device-private.json').write_text(json.dumps(device, indent=2), encoding='utf-8')
    report = dict(status='NOT_STARTED', transport='USB', mode='Switch', output_capabilities=metadata,
        configuration_commands=0, initialization_commands=0, feature_commands=0, pico_access=False,
        intended_duration_ms=120, frequency_table_hz=160, amplitude_table=80,
        physical_strength_calibrated=False, physical_stop_verified=False)
    import tkinter as tk
    root = tk.Tk(); root.title('Switch USB：仅一次短震动'); root.geometry('720x390')
    root.attributes('-topmost', True)
    label = tk.Label(root, font=('Microsoft YaHei UI', 12), justify='left', wraplength=670,
        text='保持Switch模式，Steam和飞智Engine退出，关闭手柄测试网页。\n'
             '松开全部按键、摇杆和扳机。点击后倒计时6秒，双手握住握把。\n'
             '只尝试一次低强度、约120毫秒短震动，结束发送中性停止包。\n'
             '不启用其他模式，不写配置，不操作Pico。\n'
             '如输出写入超出保护时限，会停止本轮，不自动重试。')
    label.pack(padx=20, pady=20)
    cancelled = threading.Event(); worker_done = threading.Event()
    worker = None; started = None; result_at = None; deadline = time.monotonic()+90

    def task():
        reader = writer = None; timer_active = False; timer = None
        try:
            current = enumerate_usb()
            if len(current) != 1 or current[0]['path'] != device['path']:
                raise RuntimeError('USB_TARGET_CHANGED')
            reader = Reader(device)
            baseline = observe(reader, 10, cancelled.is_set)
            report['pre_input_reports'] = len(baseline)
            report['pre_input_baseline'] = baseline
            require_neutral(baseline)
            timer = ctypes.WinDLL('winmm')
            timer_active = timer.timeBeginPeriod(1) == 0
            if not timer_active: raise RuntimeError('TIMER_UNAVAILABLE')
            writer = Writer(device)
            report['trial'] = run(writer.send, cancelled.is_set)
            writer.close(); writer = None
            # Discard queued reports, then require new live input after output has ended.
            drained = 0
            while drained < 128:
                if reader.poll() is None: break
                drained += 1
            if drained == 128: raise RuntimeError('INPUT_QUEUE_NOT_DRAINED')
            report['post_input_reports'] = len(observe(reader, 10, cancelled.is_set))
            report['status'] = report['trial']['status']
        except Exception as exc:
            report['error'] = str(exc); report['status'] = 'STOPPED_ON_FAULT'
        finally:
            if writer: writer.close()
            if reader: reader.close()
            if timer_active: report['timer_released'] = timer.timeEndPeriod(1) == 0
            (args.folder/'result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
            worker_done.set()

    def start():
        nonlocal started
        button.config(state='disabled'); started = time.monotonic()+6
        report['manual_started'] = True

    def cancel():
        cancelled.set()
        if worker is None:
            (args.folder/'result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
            root.destroy()

    button = tk.Button(root, text='开始一次短震动（6秒准备）', command=start, font=('Microsoft YaHei UI', 12))
    button.pack(pady=6); tk.Button(root, text='取消／停止', command=cancel).pack(pady=6)
    root.protocol('WM_DELETE_WINDOW', cancel)

    def poll():
        nonlocal worker, result_at
        now = time.monotonic()
        if now >= deadline: cancel()
        if cancelled.is_set() and worker is None: return
        if started is not None and worker is None and not cancelled.is_set():
            if now < started:
                label.config(text='约%d秒后检查并播放。\n双手握好，保持全部按键、摇杆和扳机松开。' % (started-now+1))
            else:
                label.config(text='正在检查并执行一次短震动，请保持全松。')
                worker = threading.Thread(target=task, daemon=False); worker.start()
        if worker_done.is_set():
            if result_at is None:
                result_at = now
                trial = report.get('trial', {})
                if trial.get('stop_error'):
                    label.config(text='停止写入未完成。若仍在震动，请正常关闭手柄。\n本轮已停止，不会自动重播。')
                else:
                    label.config(text='本轮已结束：%s\n请按实际触感反馈是否双侧可感、是否及时停止。\n写入完成不等于手柄已确认执行。' % report['status'])
            if cancelled.is_set() or now-result_at > 6:
                root.destroy(); return
        root.after(30, poll)

    root.after(100, root.lift); root.after(30, poll)
    print('SWITCH_USB_PULSE_WINDOW_READY', flush=True)
    root.mainloop()
    if worker: worker.join()
    print(report['status'], flush=True)


if __name__ == '__main__': main()
