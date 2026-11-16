"""Manually started bounded USB HID input capture. No device output API."""
import argparse
from collections import Counter
import json
from pathlib import Path
import time
from switch_usb_readonly import enumerate_usb, Reader


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--folder', type=Path, required=True)
    args = parser.parse_args()
    args.folder.mkdir(parents=True, exist_ok=False)
    devices = enumerate_usb()
    report = dict(status='NOT_STARTED', transport='USB', expected_mode='Switch',
                  device_candidates=len(devices), motor_commands=0, configuration_commands=0,
                  pico_access=False, reads=0, report_ids={}, report_lengths={}, stored_samples=0)
    if len(devices) != 1:
        report['status'] = 'AMBIGUOUS_OR_MISSING_USB_TARGET'
        (args.folder/'result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        raise ValueError('Exactly one USB 057e:2009 joystick interface required')
    device = devices[0]
    (args.folder/'device-private.json').write_text(json.dumps(device, indent=2), encoding='utf-8')
    report['device'] = {k: v for k, v in device.items() if k != 'path'}
    import tkinter as tk
    root = tk.Tk(); root.title('Switch模式 USB只读输入测试')
    root.geometry('700x360'); root.attributes('-topmost', True)
    label = tk.Label(root, font=('Microsoft YaHei UI', 12), wraplength=650, justify='left',
        text='已识别USB Pro Controller，输入64字节。\n保持Switch模式，点击开始后有6秒准备时间。\n'
             '前10秒：按右侧A、松开、下方B、松开，各做两次。\n'
             '后10秒：左摇杆左/右/上/下各推一次，最后回中。\n不发震动，不改配置，不操作Pico。')
    label.pack(padx=20, pady=20)
    reader = None; start_time = None; last_store = -1.; deadline = time.monotonic()+90
    samples = []; ids = Counter(); lengths = Counter(); changed = set(); first = None

    def finish():
        root.destroy()

    def start():
        nonlocal reader, start_time
        button.config(state='disabled')
        try:
            reader = Reader(device)
            report['manual_started'] = True
            start_time = time.monotonic()+6
        except Exception as exc:
            report['error'] = str(exc); finish()

    button = tk.Button(root, text='开始USB只读测试', command=start, font=('Microsoft YaHei UI', 12))
    button.pack(pady=5)
    tk.Button(root, text='结束／取消', command=finish).pack(pady=5)
    root.protocol('WM_DELETE_WINDOW', finish)

    def poll():
        nonlocal last_store, first
        now = time.monotonic()
        if now >= deadline or (start_time is not None and now-start_time >= 20):
            finish(); return
        if reader is not None:
            try:
                for _ in range(32):
                    packet = reader.poll()
                    if packet is None: break
                    if now < start_time or not packet: continue
                    report['reads'] += 1; ids[packet[0]] += 1; lengths[len(packet)] += 1
                    if first is None: first = packet
                    changed.update(i for i, (a, b) in enumerate(zip(packet, first)) if a != b)
                    if now-last_store >= .04 and len(samples) < 600:
                        last_store = now
                        samples.append(dict(seconds=round(now-start_time, 4), data=packet.hex()))
                if now < start_time:
                    label.config(text='准备：约%d秒后开始记录。请握好手柄，保持Switch模式。' % (start_time-now+1))
                else:
                    phase = '按右侧A、松开、下方B、松开，各做两次。' if now-start_time < 10 else '左摇杆左/右/上/下各推一次，最后回中。'
                    label.config(text='正在只读记录，剩余约%d秒。\n%s\n\n收到%d份输入报告；报告ID：%s' %
                        (max(0, 20-int(now-start_time)), phase, report['reads'],
                         ', '.join('0x%02x'%x for x in ids) or '尚无数据'))
            except Exception as exc:
                report['error'] = str(exc); finish(); return
        root.after(10, poll)

    root.after(100, root.lift); root.after(30, poll)
    print('USB_READONLY_WINDOW_READY', flush=True)
    try:
        root.mainloop()
    finally:
        if reader is not None: reader.close()
        report['report_ids'] = {'0x%02x'%k:v for k,v in ids.items()}
        report['report_lengths'] = dict(lengths)
        report['changed_byte_offsets'] = sorted(changed)
        report['stored_samples'] = len(samples)
        report['status'] = ('READ_ERROR' if report.get('error') else
            'USB_INPUT_REPORTS_OBSERVED' if report['reads'] else
            'NO_INPUT_REPORTS' if start_time is not None else 'NOT_STARTED')
        report['button_mapping_verified'] = False
        report['haptics_verified'] = False
        (args.folder/'samples-private.json').write_text(json.dumps(samples, indent=2), encoding='utf-8')
        (args.folder/'result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(report['status'], flush=True)


if __name__ == '__main__':
    main()
