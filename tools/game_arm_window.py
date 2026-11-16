"""One local, explicit arming click; contains no network or device access."""
import json,pathlib,sys,time,tkinter as tk
sys.path.insert(0,str(pathlib.Path(__file__).absolute().parents[1]/'handoff/2026-10-22/work'))
from bridge_game_phase import remaining
from game_scenarios import SCENES,scene_can_arm
scene_name=sys.argv[3] if len(sys.argv)>3 else 'door';scene=SCENES[scene_name]
arm,phase=map(pathlib.Path,sys.argv[1:3]);root=tk.Tk();root.title('本轮游戏震动测试');root.geometry('580x360' if scene_name=='dodge-attack-repeat' else '540x250');root.attributes('-topmost',True)
label=tk.Label(root,text='等待主机输入链路连接……',font=('Microsoft YaHei UI',12),wraplength=500);label.pack(pady=18)
tk.Label(root,text='先完成游戏内 L+R、A 确认，'+scene['prepare']+'。\n点击后等1秒，再'+scene['action']+'。未点击时只转发按键。',wraplength=500).pack()
def click():
    try:
        current=json.loads(phase.read_text(encoding='utf-8'))
        if not scene_can_arm(scene_name,current,time.monotonic()):return
        with arm.open('x',encoding='utf-8') as h:json.dump(dict(requested_at_monotonic=time.monotonic()),h)
        button.configure(state='disabled');label.configure(text='已请求启用，等待确认……')
    except (OSError,ValueError):button.configure(state='disabled')
button=tk.Button(root,text='已到测试位置，启用本轮震动',command=click,state='disabled',font=('Microsoft YaHei UI',12));button.pack(pady=16)
def poll():
    try:
        data=json.loads(phase.read_text(encoding='utf-8'));state=data['phase'];seconds=remaining(data,time.monotonic());left=0 if seconds is None else int(seconds)
        if state=='ENDED':
            label.configure(text='本轮已结束，请等待日志和停止状态核对。');button.configure(state='disabled');root.after(2500,root.destroy);return
        if state=='ARMED':label.configure(text=f'震动已启用：等1秒后{scene["action"]}。剩余约{left}秒');button.configure(state='disabled')
        elif state=='INPUT_READY':
            label.configure(text=f'仅按键转发，尚未启用震动。剩余约{left}秒')
            ready=scene_can_arm(scene_name,data,time.monotonic())
            if scene_name=='dodge-attack-repeat' and not ready:label.configure(text=f'尚未启用；两组动作需预留超过20秒。当前剩余约{left}秒，请勿赶操作。')
            button.configure(state='normal' if ready and not arm.exists() else 'disabled')
    except (OSError,ValueError,KeyError):pass
    root.after(200,poll)
root.after(200,poll);root.mainloop()
