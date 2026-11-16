"""One manual60second trial window; no device access."""
import json,pathlib,sys,time,tkinter as tk
arm,phase=map(pathlib.Path,sys.argv[1:3]);root=tk.Tk();root.title('Final60second game trial');root.geometry('750x350');root.attributes('-topmost',True)
label=tk.Label(root,text='Wait for PC precheck. Pico stays BOOTSEL until explicit swap instruction.',wraplength=700,font=('Microsoft YaHei UI',13));label.pack(pady=20)
tk.Label(root,text='Register controller and enter game, release all controls.\nClick ENABLE. Follow six green cues at5/15/25/35/45/55 seconds: one B then A each.\nAfter60second output ends, move stick once then release ALL controls until test ends.',wraplength=700).pack()
def allowed(s,now):return s.get('phase')=='INPUT_READY' and s.get('source_neutral_ready') is True and s.get('clock')=='monotonic' and s.get('deadline_monotonic',now)-now>70

def click():
    try:
        s=json.loads(phase.read_text());now=time.monotonic()
        if not allowed(s,now):return
        with arm.open('x') as f:json.dump(dict(requested_at_monotonic=now),f)
        button.configure(state='disabled')
    except (OSError,ValueError):button.configure(state='disabled')
button=tk.Button(root,text='ENABLE ONE60SECOND TEST',state='disabled',command=click);button.pack(pady=10)
def cancel():arm.with_suffix('.cancel').write_text('cancel');root.destroy()
root.protocol('WM_DELETE_WINDOW',cancel);tk.Button(root,text='Cancel / stop',command=cancel).pack()
def poll():
    try:
        s=json.loads(phase.read_text());state=s.get('phase');now=time.monotonic();color='black'
        text={'DISCOVERING':'Wait for explicit swap instruction.','WAITING_SOURCE':'Waiting for configured fresh neutral source500ms.','INPUT_READY':'Complete game registration, release controls, then click ENABLE.','MUTED':'Output stopped. Move stick once to confirm, then release ALL controls until the end.','MUTED_FAULT':'Protection triggered; no automatic retry. Wait for collection.','ENDED':'Test ended; wait for BOOTSEL collection instruction.'}.get(state,'Waiting...')
        if state=='ARMED':
            left=s.get('armed_seconds_left',60);elapsed=60-left;index=int((elapsed-5)//10)
            if 0<=index<6 and 5+10*index<=elapsed<9+10*index:text=f'NOW action{index+1}/6: B then A, then release.';color='green'
            else:text='Wait for next green action cue; do not trigger early.'
            text+=f'  Remaining{left:.1f}s; completed{s.get("completed_events",0)}/6'
        label.configure(text=text,fg=color);button.configure(state='normal' if allowed(s,now) and not arm.exists() else 'disabled')
        if state=='ENDED':root.after(5000,root.destroy);return
    except (OSError,ValueError,TypeError):pass
    root.after(100,poll)
root.after(100,poll);root.mainloop()
