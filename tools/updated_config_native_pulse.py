"""Manual ordinary XInput pulse with current-configuration readback; no HID mode/stream."""
import pathlib,sys,json,datetime,importlib.util,time,tkinter as tk
ROOT=pathlib.Path(__file__).absolute().parents[1];WORK=ROOT/'handoff/2026-10-22/work';PRIVATE=WORK/'private'
sys.path.insert(0,str(WORK))
def pulse(set_levels,index,sleep=time.sleep):
    try:
        set_levels(index,4096,4096);sleep(.180)
    finally:set_levels(index,0,0)
def main():
    from bridge_windows import load_owner,XInputSource
    from bridge_input import NEUTRAL
    stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S');report=dict(status='INCOMPLETE',persistent_commands=0,custom_hid_mode_commands=0,level=4096,nominal_ms=180,manual_clicked=False,stop_api_success=False)
    owner=reader=None
    try:
        reference=max(PRIVATE.glob('driver-update-config-*.json'),key=lambda f:f.stat().st_mtime);expected=json.loads(reference.read_text())
        owner=load_owner();reader=owner.safe.open_reader({});identity=owner.safe.digest(reader.ask(4,reply_size=16))
        if identity!=expected['identity_sha256']:raise ValueError('Controller identity changed')
        before=dict(device=dict(identity_sha256=identity),state_before=list(reader.state()),ram={})
        for rid,label in ((1,'global'),(4,'mapping'),(5,'lighting'),(6,'motors')):
            data,summary=owner.safe.read_ram(reader,rid)
            if data.hex()!=expected['ram'][label]['raw_hex']:raise ValueError('Current configuration changed since new backup: '+label)
            before['ram'][label]=dict(ram_id=rid,raw_hex=data.hex(),**summary)
        with (PRIVATE/('updated-native-backup-'+stamp+'.json')).open('x',encoding='utf-8') as f:json.dump(before,f,indent=2)
        spec=importlib.util.spec_from_file_location('native_xi',WORK/'flydigi-xinput.py');xi=importlib.util.module_from_spec(spec);spec.loader.exec_module(xi)
        source=XInputSource();index=xi.flydigi_index()
        if source.slot!=index or source()!=NEUTRAL:raise ValueError('Release controls or slot mismatch')
        root=tk.Tk();root.title('Updated config: ordinary XInput pulse');root.geometry('620x260');root.attributes('-topmost',True);ready=[False]
        label=tk.Label(root,text='One ordinary low XInput pulse: 180ms, 4096/65535.\nClick START, then hold both grips during 6s countdown.\nNo configuration writes; Pico stays BOOTSEL.',wraplength=580);label.pack(pady=25)
        def countdown(n):
            label.configure(text='Prepare both grips: '+str(n))
            if n:root.after(1000,lambda:countdown(n-1))
            else:ready[0]=True;root.destroy()
        def click():report['manual_clicked']=True;button.configure(state='disabled');countdown(6)
        button=tk.Button(root,text='START ONE PULSE',command=click);button.pack();root.after(90000,root.destroy);root.mainloop()
        if not ready[0]:raise ValueError('Cancelled before pulse')
        if source()!=NEUTRAL:raise ValueError('Controls not released before pulse')
        started=time.perf_counter();pulse(xi.set_levels,index);report.update(stop_api_success=True,elapsed_ms=(time.perf_counter()-started)*1000)
        owner.verify(reader,before,report)
        if not report['configuration_unchanged']:raise ValueError('Configuration readback differs')
        report['status']='PASSED_NATIVE_PULSE_API_STOP_AND_CURRENT_CONFIG_PENDING_HUMAN'
    except BaseException as e:report['error']=repr(e)
    finally:
        if reader:reader.close()
        if owner:owner.safe.ro.lib.hid_exit()
        out=ROOT/'docs'/('UPDATED_CONFIG_NATIVE_PULSE_'+stamp+'.json');out.write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2));print(out)
    return 0 if report['status'].startswith('PASSED_') else 1
if __name__=='__main__':raise SystemExit(main())
