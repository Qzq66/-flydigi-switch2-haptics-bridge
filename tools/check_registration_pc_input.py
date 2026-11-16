"""Manually started PC registration-button XInput-only diagnostic; no HID output/configuration API."""
import datetime,json,pathlib,sys,time,tkinter as tk
ROOT=pathlib.Path(__file__).absolute().parents[1];sys.path.insert(0,str(ROOT/'handoff/2026-10-22/work'))
from bridge_windows import XInputSource
from bridge_input import convert,NEUTRAL

def main():
    report=dict(status='NOT_STARTED',motor_commands=0,configuration_commands=0,pico_access=False,manual_started=False,reads=0,raw_button_reads=0,nonneutral_pro_reads=0,changes=[])
    source=None;root=tk.Tk();root.title('只读登记按键诊断：L、R、A');root.geometry('600x310');root.attributes('-topmost',True)
    label=tk.Label(root,text='Pico保持电脑BOOTSEL，飞智接收器保持电脑原位。\n点击开始后准备3秒，再短按L、R分别按一次，再同时按L+R，最后右侧A按一次并松开。\n只读XInput，不改模式、不改配置、不输出震动。',wraplength=560,font=('Microsoft YaHei UI',11));label.pack(pady=20)
    deadline=time.monotonic()+45;started=None;previous=None
    def finish():
        report['status']=('OBSERVED_PC_INPUT' if report['raw_button_reads'] and report['nonneutral_pro_reads'] else 'NO_PC_BUTTON_INPUT_OBSERVED') if report['manual_started'] else 'NOT_STARTED'
        root.destroy()
    def click():
        nonlocal source,started
        try:source=XInputSource();report['slot']=source.slot
        except BaseException as exc:report['error']=repr(exc);root.destroy();return
        report['manual_started']=True;started=time.monotonic()+3;button.configure(state='disabled')
    button=tk.Button(root,text='开始只读记录',command=click);button.pack(pady=10);tk.Button(root,text='取消／结束',command=finish).pack();root.protocol('WM_DELETE_WINDOW',finish)
    def poll():
        nonlocal previous
        now=time.monotonic()
        if started is None:
            if now>=deadline:finish();return
        elif now<started:label.configure(text=f'准备：{max(1,int(started-now)+1)}秒后开始，随后按L、R、L+R、右侧A。')
        elif now-started>=12:finish();return
        else:
            try:
                state=source.xi.read(source.slot)
                if state is None:raise RuntimeError('XInput source disconnected')
                value=convert(state.gamepad);buttons=int(state.gamepad.buttons);report['reads']+=1
                report['raw_button_reads']+=int(bool(buttons));report['nonneutral_pro_reads']+=int(value!=NEUTRAL)
                key=(buttons,value.hex())
                if key!=previous:
                    if len(report['changes'])<128:report['changes'].append(dict(seconds=now-started,raw_buttons=buttons,pro_input=value.hex()))
                    previous=key
                label.configure(text=f'正在只读记录，剩余约{max(0,12-int(now-started))}秒。\n请短按L、R分别按一次，再同时按L+R，最后右侧A按一次，然后全松。\n已读{report["reads"]}次；有按键{report["raw_button_reads"]}次。')
            except BaseException as exc:report['error']=repr(exc);root.destroy();return
        root.after(10,poll)
    root.after(50,poll);root.mainloop()
    if report.get('error'):report['status']='INPUT_DIAGNOSTIC_ERROR'
    stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S');out=ROOT/'docs'/('PC_REGISTRATION_INPUT_'+stamp+'.json')
    with out.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
    print(json.dumps({k:v for k,v in report.items() if k!='changes'},indent=2));print(out)
    return 0 if report['status']=='OBSERVED_PC_INPUT' else 1

if __name__=='__main__':raise SystemExit(main())
