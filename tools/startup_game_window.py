"""Manual Switch game arming window; no devices or sockets."""
import json,pathlib,sys,time,tkinter as tk
from fidelity_game_policy import can_click
arm,phase=map(pathlib.Path,sys.argv[1:3]);root=tk.Tk();root.title('Switch实时双频：最多三事件候选');root.geometry('640x370');root.attributes('-topmost',True)
label=tk.Label(root,text='等待电脑预检及主机链路……',wraplength=600,font=('Microsoft YaHei UI',12));label.pack(pady=18)
tk.Label(root,text='先完成主机登记、游戏内L+R和A确认。\n到此前B闪避→A攻击的位置，松开全部按键、摇杆和扳机。\n点击并看到已启用后等1秒，完成三组B→松开→A→全松，每组震动停止后至少等1秒。\n最多三次活动，每次每侧320ms、±9；第三次后停止。\n震动结束后等1秒，轻推摇杆验证仍可移动，再全松。',wraplength=600).pack()
def click():
    try:
        status=json.loads(phase.read_text());now=time.monotonic()
        if not can_click(status,now):return
        with arm.open('x') as f:json.dump(dict(requested_at_monotonic=now),f)
        button.configure(state='disabled')
    except (OSError,ValueError):button.configure(state='disabled')
button=tk.Button(root,text='已到战斗位置并全松，启用最多三次双频',state='disabled',command=click);button.pack(pady=14)
def cancel():arm.with_suffix('.cancel').write_text('cancel');root.destroy()
root.protocol('WM_DELETE_WINDOW',cancel);tk.Button(root,text='取消／停止本轮',command=cancel).pack()
def poll():
    try:
        s=json.loads(phase.read_text());state=s.get('phase');now=time.monotonic();left=max(0,int(s.get('deadline_monotonic',now)-now))
        text={'DISCOVERING':'电脑已完成全松检查，等待按明确提示换接Pico。','INPUT_READY':f'只转发按键，尚未启用震动。剩余约{left}秒。','ARMED':f'已完成{s.get("completed_events",0)}/3；剩余约{s.get("armed_seconds_left",15):.1f}秒。每组停止后至少等1秒，再做下一组B→A。','MUTED':'双频已停止且不重播。等1秒后轻推摇杆验证操控，再全松。','ENDED':'本轮已结束，请等待配置和Flash日志核对。'}.get(state,'等待预检……')
        if state=='WAITING_SOURCE':text='\u7b49\u5f85\u4e3b\u673a\u6e90\u5b8c\u6210\u521d\u59cb\u5316\u5e76\u8fde\u7eed\u5b89\u9759500\u6beb\u79d2\u3002\u9707\u52a8\u542f\u7528\u6309\u94ae\u6682\u4e0d\u53ef\u7528\u3002'
        if state=='MUTED_FAULT':text='网络或输出保护已触发，震动已禁用且不会重启。正在限时回收日志；本轮不会计为通过。'
        if state=='INPUT_READY' and not s.get('source_neutral_ready'):text+=' 等待主机马达字段回中并安静500ms。'
        label.configure(text=text);button.configure(state='normal' if can_click(s,now) and not arm.exists() else 'disabled')
        if state=='ENDED':root.after(4000,root.destroy);return
    except (OSError,ValueError,KeyError):pass
    root.after(150,poll)
root.after(150,poll);root.mainloop()
