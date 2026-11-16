"""Manual bounded all-slot XInput observer; no HID output or configuration API."""
import pathlib,sys,json,time,datetime,tkinter as tk
ROOT=pathlib.Path(__file__).absolute().parents[1];sys.path.insert(0,str(ROOT/'handoff/2026-10-22/work'))
import xinput_readonly as xi

def main():
    root=tk.Tk();root.title('All XInput slots - read only');root.geometry('700x380');root.attributes('-topmost',True)
    report=dict(status='NOT_STARTED',motor_commands=0,configuration_commands=0,pico_access=False,slots={str(i):dict(reads=0,connected_reads=0,button_reads=0,movement_reads=0,changes=[],omitted_changes=0) for i in range(4)})
    label=tk.Label(root,text='Click START, wait 3 seconds, then press right A, lower B, L+R and move a stick.\nPico stays BOOTSEL. No rumble or configuration commands.',font=('Segoe UI',11),wraplength=660);label.pack(pady=20)
    started=None;deadline=time.monotonic()+90;previous={}
    def start():
        nonlocal started
        started=time.monotonic()+3;report['status']='RECORDING';button.configure(state='disabled')
    def finish():
        report['status']='COMPLETED_ALL_SLOT_OBSERVATION' if started is not None else 'NOT_STARTED';root.destroy()
    button=tk.Button(root,text='START',command=start);button.pack(pady=10);tk.Button(root,text='END',command=finish).pack();root.protocol('WM_DELETE_WINDOW',finish)
    def poll():
        now=time.monotonic()
        if started is None:
            if now>=deadline:finish();return
        elif now<started:label.configure(text='Prepare: '+str(max(1,int(started-now)+1)))
        elif now-started>=16:finish();return
        else:
            rows=[]
            try:
                for i in range(4):
                    s=xi.read(i);r=report['slots'][str(i)];r['reads']+=1
                    if s is None:rows.append(str(i)+': disconnected');continue
                    g=s.gamepad;r['connected_reads']+=1;r['button_reads']+=int(bool(g.buttons));r['movement_reads']+=int(any(abs(v)>8000 for v in (g.lx,g.ly,g.rx,g.ry)) or g.lt>30 or g.rt>30)
                    v=(int(g.buttons),int(g.lt),int(g.rt),int(g.lx),int(g.ly),int(g.rx),int(g.ry))
                    if v!=previous.get(i):
                        if len(r['changes'])<128:r['changes'].append(dict(seconds=now-started,packet=int(s.packet),values=v))
                        else:r['omitted_changes']+=1
                        previous[i]=v
                    rows.append(str(i)+': buttons='+hex(g.buttons)+' packet='+str(s.packet)+' button reads='+str(r['button_reads']))
                label.configure(text='Press A, B, L+R; move stick; release. Remaining '+str(max(0,16-int(now-started)))+'s\n\n'+'\n'.join(rows))
            except BaseException as e:report['error']=repr(e);root.destroy();return
        root.after(15,poll)
    root.after(50,poll);root.mainloop()
    out=ROOT/'docs'/('ALL_XINPUT_SLOTS_'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'.json')
    with out.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
    print(json.dumps(dict(status=report['status'],error=report.get('error'),slots={k:{n:v[n] for n in ('connected_reads','button_reads','movement_reads','omitted_changes')} for k,v in report['slots'].items()}),indent=2));print(out)
if __name__=='__main__':main()
