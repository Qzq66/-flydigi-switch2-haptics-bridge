"""One local arming button; no HID, USB, sockets or automatic replay."""
import json,pathlib,sys,time,tkinter as tk
arm,phase=map(pathlib.Path,sys.argv[1:3])
root=tk.Tk();root.title('幅度对照：160Hz，±4 / ±8');root.geometry('600x340');root.attributes('-topmost',True)
label=tk.Label(root,text='等待设备、备份和全松检查……',wraplength=560,font=('Microsoft YaHei UI',12));label.pack(pady=20)
tk.Label(root,text='双手分别握住左右握把，松开按键、摇杆和扳机。\n两段均160Hz、200ms；A：峰值±4；B：峰值±8。\n点击后先倒计时6秒；A停止并确认关闭后，至少静默5秒再播B。\n每段只播一次，不换接Pico或操作Switch。',wraplength=560).pack()

def click():
    try:
        p=json.loads(phase.read_text(encoding='utf-8'));now=time.monotonic()
        if p.get('phase')!='READY' or p.get('clock')!='monotonic' or now>=p['deadline_monotonic']:return
        with arm.open('x',encoding='utf-8') as out:json.dump(dict(requested_at_monotonic=now),out)
        button.configure(state='disabled');label.configure(text='已请求，等待程序确认……')
    except (OSError,ValueError,KeyError):button.configure(state='disabled')
button=tk.Button(root,text='已握好，开始本轮A/B',command=click,state='disabled',font=('Microsoft YaHei UI',12));button.pack(pady=20)

def cancel():
    arm.with_suffix('.cancel').write_text('cancel',encoding='utf-8');root.destroy()
root.protocol('WM_DELETE_WINDOW',cancel)
tk.Button(root,text='取消／停止本轮',command=cancel).pack()

def poll():
    try:
        p=json.loads(phase.read_text(encoding='utf-8'));state=p['phase'];now=time.monotonic()
        texts={'PREPARE':'已确认，准备倒计时6秒，保持全松。','A':'正在播放A：160Hz、±4短片段。','GAP':'A已停止并确认关闭，静默至少5秒，保持握好。','B':'正在播放B：160Hz、±8短片段。','ENDED':'程序已结束，请等待停止、配置和体感核对。'}
        if state=='READY':
            left=max(0,int(p['deadline_monotonic']-now));label.configure(text=f'设备和全松检查通过。剩余{left}秒可开始。')
            button.configure(state='normal' if left>0 and not arm.exists() else 'disabled')
        else:label.configure(text=texts.get(state,'等待设备、备份和全松检查……'));button.configure(state='disabled')
        if state=='ENDED':root.after(4000,root.destroy);return
    except (OSError,ValueError,KeyError):pass
    root.after(100,poll)
root.after(100,poll);root.mainloop()
