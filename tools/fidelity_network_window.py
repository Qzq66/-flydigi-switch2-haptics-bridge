"""Manual PC-only network replay arming and cancellation, no hardware API."""
import json,pathlib,sys,time,tkinter as tk
arm,phase=map(pathlib.Path,sys.argv[1:3]);root=tk.Tk();root.title('双频真实网络短片段回放');root.geometry('620x330');root.attributes('-topmost',True)
label=tk.Label(root,text='等待RAM Pico、网络、备份和全松检查……',wraplength=580,font=('Microsoft YaHei UI',12));label.pack(pady=20)
tk.Label(root,text='Pico和飞智都留在电脑，不连接Switch。\n单次回放捕获的双频片段，最多每侧320ms活动、±12。\n点击后倒计时6秒，请双手握住握把并保持按键/摇杆/扳机全松。\n结束不自动重播；Pico回BOOTSEL后核对完整Flash。',wraplength=580).pack()
def click():
    try:
        p=json.loads(phase.read_text());now=time.monotonic()
        if p.get('phase')!='READY' or p.get('clock')!='monotonic' or now>=p['deadline_monotonic']:return
        with arm.open('x') as f:json.dump(dict(requested_at_monotonic=now),f)
        button.configure(state='disabled')
    except (OSError,ValueError,KeyError):button.configure(state='disabled')
button=tk.Button(root,text='已握好，开始一次网络回放',command=click,state='disabled');button.pack(pady=15)
def cancel():arm.with_suffix('.cancel').write_text('cancel');root.destroy()
root.protocol('WM_DELETE_WINDOW',cancel);tk.Button(root,text='取消／停止本轮',command=cancel).pack()
def poll():
    try:
        p=json.loads(phase.read_text());state=p['phase'];now=time.monotonic()
        text={'PREPARE':'准备倒计时6秒，保持握好。','ACTIVE':'正在通过RAM Pico/Wi-Fi回放一次双频片段。','MUTED':'输出已停止，仍在核对收包和输入链路。','ENDED':'本轮已结束，等待停止、Flash和配置核对。'}.get(state,'等待RAM Pico、网络、备份和全松检查……')
        if state=='READY':text=f'设备/网络/全松检查通过。剩余{max(0,int(p["deadline_monotonic"]-now))}秒可开始。'
        label.configure(text=text);button.configure(state='normal' if state=='READY' and now<p['deadline_monotonic'] and not arm.exists() else 'disabled')
        if state=='ENDED':root.after(4000,root.destroy);return
    except (OSError,ValueError,KeyError):pass
    root.after(100,poll)
root.after(100,poll);root.mainloop()
