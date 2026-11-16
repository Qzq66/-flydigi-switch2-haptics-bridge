"""Read-only, ordered controller liveness gate; adapters imported only by main."""
import json,pathlib,time

NEUTRAL=bytes.fromhex('000000000880000880')
RIGHT=bytes.fromhex('080000000880000880')
LOWER=bytes.fromhex('040000000880000880')

class Liveness:
    def __init__(self):
        self.stage=0;self.quiet=None;self.last=None;self.transitions=[]

    def feed(self,value,now):
        if self.last is not None and now<self.last:raise ValueError('Clock reversed')
        self.last=now
        if self.stage==5:return True
        expected=(NEUTRAL,RIGHT,NEUTRAL,LOWER,NEUTRAL)[self.stage]
        if value!=expected:
            self.quiet=None
            return False
        if self.quiet is None:self.quiet=now
        hold=(.5,0,.15,0,.5)[self.stage]
        if now-self.quiet>=hold:
            self.transitions.append(dict(stage=self.stage,at=now));self.stage+=1;self.quiet=None
        return self.stage==5

def passed(report):
    return (report.get('status')=='PASSED_ORDERED_PC_INPUT_LIVENESS'
        and report.get('manual_started') is True and report.get('slot') in (0,1,2,3)
        and report.get('motor_commands')==0 and report.get('configuration_commands')==0
        and report.get('final_pro_input')==NEUTRAL.hex()
        and [v.get('stage') for v in report.get('transitions',[])]==list(range(5))
        and not report.get('error'))

def main():
    import sys,tkinter as tk
    root_path=pathlib.Path(__file__).absolute().parents[1]
    sys.path.insert(0,str(root_path/'handoff/2026-10-22/work'))
    from bridge_windows import XInputSource
    out=pathlib.Path(sys.argv[1]);gate=Liveness();source=None;deadline=time.monotonic()+45
    report=dict(status='CANCELLED_OR_TIMED_OUT',manual_started=False,motor_commands=0,configuration_commands=0)
    root=tk.Tk();root.title('主机测试前：只读按键响应检查');root.geometry('620x250');root.attributes('-topmost',True)
    label=tk.Label(root,text='Pico保持电脑BOOTSEL。点击开始后，按窗口逐步操作。\n只读检查，不输出震动或修改配置。',font=('Microsoft YaHei UI',12));label.pack(pady=30)
    def start():
        nonlocal source
        try:source=XInputSource();report.update(manual_started=True,slot=source.slot);button.configure(state='disabled')
        except Exception as exc:report['error']=repr(exc);root.destroy()
    button=tk.Button(root,text='开始检查',command=start);button.pack()
    tk.Button(root,text='取消',command=root.destroy).pack();root.protocol('WM_DELETE_WINDOW',root.destroy)
    prompts=('松开全部按键、摇杆和扳机，保持半秒','短按右侧 A 键','松开全部控制','短按下方 B 键','松开全部控制，保持半秒')
    def poll():
        if time.monotonic()>=deadline:root.destroy();return
        if source:
            try:
                value=source();report['final_pro_input']=value.hex()
                if gate.feed(value,time.monotonic()):report['status']='PASSED_ORDERED_PC_INPUT_LIVENESS';root.destroy();return
                label.configure(text=prompts[gate.stage]+'\nPico仍留电脑，不换接。')
            except Exception as exc:report['error']=repr(exc);root.destroy();return
        root.after(10,poll)
    root.after(10,poll);root.mainloop();report['transitions']=gate.transitions
    with out.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
    return 0 if passed(report) else 1

if __name__=='__main__':raise SystemExit(main())
