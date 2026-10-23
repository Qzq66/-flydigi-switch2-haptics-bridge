"""One local, explicit arming click; contains no network or device access."""
import json,pathlib,sys,time,tkinter as tk
sys.path.insert(0,str(pathlib.Path(__file__).absolute().parents[1]/'handoff/2026-10-22/work'))
from bridge_game_phase import remaining,can_arm
arm,phase=map(pathlib.Path,sys.argv[1:3]);root=tk.Tk();root.title('本轮游戏震动测试');root.geometry('540x250');root.attributes('-topmost',True)
label=tk.Label(root,text='等待主机输入链路连接……',font=('Microsoft YaHei UI',12),wraplength=500);label.pack(pady=18)
tk.Label(root,text='先完成游戏内 L+R、A 确认，停在门前并松开摇杆。\n点击后等1秒，再进门一次。未点击时只转发按键。',wraplength=500).pack()
def click():
    try:
        current=json.loads(phase.read_text(encoding='utf-8'))
        if not can_arm(current,time.monotonic()):return
        with arm.open('x',encoding='utf-8') as h:json.dump(dict(requested_at_monotonic=time.monotonic()),h)
        button.configure(state='disabled');label.configure(text='已请求启用，等待确认……')
    except (OSError,ValueError):button.configure(state='disabled')
button=tk.Button(root,text='已在门前，启用本轮震动',command=click,state='disabled',font=('Microsoft YaHei UI',12));button.pack(pady=16)
def poll():
    try:
        data=json.loads(phase.read_text(encoding='utf-8'));state=data['phase'];seconds=remaining(data,time.monotonic());left=0 if seconds is None else int(seconds)
        if state=='ENDED':
            label.configure(text='本轮已结束，请等待日志和停止状态核对。');button.configure(state='disabled');root.after(2500,root.destroy);return
        if state=='ARMED':label.configure(text=f'震动已启用：等1秒后进门一次。剩余约{left}秒');button.configure(state='disabled')
        elif state=='INPUT_READY':
            label.configure(text=f'仅按键转发，尚未启用震动。剩余约{left}秒')
            button.configure(state='normal' if can_arm(data,time.monotonic()) and not arm.exists() else 'disabled')
    except (OSError,ValueError,KeyError):pass
    root.after(200,poll)
root.after(200,poll);root.mainloop()
