"""Read-only Windows joystick input observer, including non-XInput Switch modes."""
import argparse
import ctypes as c
import json
from pathlib import Path
import time


class Position(c.Structure):
    _fields_ = [(n, c.c_uint32) for n in ('size', 'flags', 'x', 'y', 'z', 'r', 'u', 'v',
                                      'buttons', 'button_number', 'pov', 'reserved1', 'reserved2')]


class Caps(c.Structure):
    _fields_ = [('mid', c.c_uint16), ('pid', c.c_uint16), ('name', c.c_wchar * 32)] + [
        (n, c.c_uint32) for n in ('xmin', 'xmax', 'ymin', 'ymax', 'zmin', 'zmax', 'buttons',
                                'period_min', 'period_max', 'rmin', 'rmax', 'umin', 'umax',
                                'vmin', 'vmax', 'flags', 'max_axes', 'axes', 'max_buttons')] + [
        ('regkey', c.c_wchar * 32), ('oem', c.c_wchar * 260)]


def backend():
    dll = c.WinDLL('winmm.dll')
    dll.joyGetNumDevs.restype = c.c_uint
    dll.joyGetDevCapsW.argtypes = [c.c_size_t, c.POINTER(Caps), c.c_uint]
    dll.joyGetDevCapsW.restype = c.c_uint
    dll.joyGetPosEx.argtypes = [c.c_uint, c.POINTER(Position)]
    dll.joyGetPosEx.restype = c.c_uint
    return dll


def position(dll, slot):
    value = Position(size=c.sizeof(Position), flags=0xff)
    code = dll.joyGetPosEx(slot, c.byref(value))
    return code, value


def inventory(dll):
    found = []
    for slot in range(min(dll.joyGetNumDevs(), 32)):
        caps = Caps()
        if dll.joyGetDevCapsW(slot, c.byref(caps), c.sizeof(caps)):
            continue
        status, _ = position(dll, slot)
        if status == 0:
            found.append(dict(slot=slot, name=caps.name, manufacturer_id=caps.mid,
                              product_id=caps.pid, buttons=caps.buttons, axes=caps.axes))
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', action='store_true')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    dll = backend()
    devices = inventory(dll)
    if args.inventory:
        print(json.dumps(devices, ensure_ascii=True))
        return
    if args.report is None or args.report.exists():
        parser.error('a new report path is required')
    import tkinter as tk
    root = tk.Tk()
    root.title('Switch模式：只读按键与摇杆测试')
    root.geometry('720x440')
    root.attributes('-topmost', True)
    report = dict(status='NOT_STARTED', backend='winmm_readonly', devices=devices,
                  pico_access=False, motor_commands=0, configuration_commands=0,
                  mode_changed=False, physical_identity_verified=False, observations={})
    label = tk.Label(root, wraplength=680, justify='left', font=('Microsoft YaHei UI', 11))
    label.pack(padx=15, pady=20)
    label.config(text='保持手柄Switch模式。点击开始后等待3秒，再按右侧A、下方B并松开，\n'
                      '推动左摇杆左右、上下，再回中；不要操作其他手柄。\n'
                      '仅观察电脑当前输入，不测试震动，不连接或刷写Pico。\n\n' +
                      '\n'.join('槽位%d：%s（%d键，%d轴）' % (x['slot'], x['name'], x['buttons'], x['axes']) for x in devices))
    started = None
    previous = {}
    baselines = {}
    deadline = time.monotonic() + 90

    def finish():
        if started is not None:
            report['status'] = 'OBSERVED_WINDOWS_BUTTON_AND_AXIS_INPUT' if any(
                x['button_transitions'] and x['max_axis_delta'] > 4096
                for x in report['observations'].values()) else 'INCOMPLETE_INPUT_OBSERVATION'
        root.destroy()

    def start():
        nonlocal started
        started = time.monotonic() + 3
        button.config(state='disabled')
        for device in devices:
            slot = device['slot']
            report['observations'][str(slot)] = dict(reads=0, errors=0, button_transitions=0,
                pressed_masks=[], released_after_press=False, max_axis_delta=0)

    button = tk.Button(root, text='开始只读检查（保持Switch模式）', command=start, state='normal' if devices else 'disabled')
    button.pack(pady=8)
    tk.Button(root, text='结束／取消', command=finish).pack(pady=8)
    root.protocol('WM_DELETE_WINDOW', finish)

    def poll():
        now = time.monotonic()
        if now >= deadline or (started is not None and now-started >= 15):
            finish()
            return
        if started is not None:
            if now < started:
                label.config(text='准备：%d秒后开始。保持Switch模式，双手握好手柄。' % (started-now+1))
            else:
                summaries = []
                for device in devices:
                    slot = device['slot']
                    item = report['observations'][str(slot)]
                    code, value = position(dll, slot)
                    if code:
                        item['errors'] += 1
                        continue
                    item['reads'] += 1
                    axes = (value.x, value.y, value.z, value.r, value.u, value.v)
                    baseline = baselines.setdefault(slot, axes)
                    item['max_axis_delta'] = max(item['max_axis_delta'], max(abs(a-b) for a, b in zip(axes, baseline)))
                    if slot in previous and previous[slot] != value.buttons:
                        item['button_transitions'] += 1
                    previous[slot] = value.buttons
                    if value.buttons and value.buttons not in item['pressed_masks'] and len(item['pressed_masks']) < 32:
                        item['pressed_masks'].append(value.buttons)
                    if not value.buttons and item['pressed_masks']:
                        item['released_after_press'] = True
                    summaries.append('槽位%d：按键变化%d次，摇杆最大变化%d' % (slot, item['button_transitions'], item['max_axis_delta']))
                label.config(text='请按A、B并松开，移动左摇杆左右、上下，再回中。\n剩余约%d秒\n\n%s' %
                             (max(0, 15-int(now-started)), '\n'.join(summaries)))
        root.after(20, poll)

    root.after(300, root.lift)
    root.after(50, poll)
    root.mainloop()
    with args.report.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2, ensure_ascii=True)
    print(report['status'])


if __name__ == '__main__':
    main()
