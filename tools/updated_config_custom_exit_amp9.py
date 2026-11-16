"""Manual ordinary XInput pulse with current-configuration readback; no HID mode/stream."""
import pathlib,sys,json,datetime,importlib.util,time,math,tkinter as tk
ROOT=pathlib.Path(__file__).absolute().parents[1];WORK=ROOT/'handoff/2026-10-22/work';PRIVATE=WORK/'private'
sys.path.insert(0,str(WORK))
def pulse(set_levels,index,sleep=time.sleep):
    try:
        set_levels(index,4096,4096);sleep(.180)
    finally:set_levels(index,0,0)
def main():
    from bridge_windows import load_owner,XInputSource,TimerResolution
    from bridge_input import NEUTRAL
    stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S');report=dict(status='INCOMPLETE',persistent_commands=0,custom_hid_mode_commands=0,level=4096,nominal_ms=180,manual_clicked=False,stop_api_success=False)
    owner=reader=None;timer=None
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
        root=tk.Tk();root.title('Updated config: custom then ordinary pulse');root.geometry('620x260');root.attributes('-topmost',True);ready=[False]
        label=tk.Label(root,text='Custom +/-9 pulse 120ms, then >=5s quiet, then ordinary180ms.\nClick START, then hold both grips during 6s countdown.\nNo configuration writes; Pico stays BOOTSEL.',wraplength=580);label.pack(pady=25)
        def countdown(n):
            label.configure(text='Prepare both grips: '+str(n))
            if n:root.after(1000,lambda:countdown(n-1))
            else:ready[0]=True;root.destroy()
        def click():report['manual_clicked']=True;button.configure(state='disabled');countdown(6)
        button=tk.Button(root,text='START TWO CHECKS',command=click);button.pack();root.after(90000,root.destroy);root.mainloop()
        if not ready[0]:raise ValueError('Cancelled before pulse')
        if source()!=NEUTRAL:raise ValueError('Controls not released before pulse')
        timer=TimerResolution()
        if not timer.start():raise RuntimeError('Timer resolution acquisition failed')
        report['custom_hid_mode_commands']=True
        reader.allowed_modes=owner.MODES;reader.maximum_offset=9
        started=time.perf_counter();frames=0
        try:
            reader.mode(b'\x01\x12\x02\x40\x00')
            target=time.perf_counter()
            for block in range(15):
                now=time.perf_counter()
                if now-target>.004:raise RuntimeError('Custom dispatch late; no catch-up')
                samples=[128+round(9*math.sin(2*math.pi*160*(block*8+i)/1000)) for i in range(8)]
                reader.stream(owner.safe.waveform(samples,samples,maximum_offset=9));frames+=1
                target+=.008;time.sleep(max(0.,target-time.perf_counter()))
        finally:
            owner.stop(reader,report)
        report.update(custom_frames=frames,custom_elapsed_ms=(time.perf_counter()-started)*1000)
        owner.verify(reader,before,report)
        if not report['configuration_unchanged']:raise ValueError('Configuration changed after custom stop')
        quiet=time.perf_counter();time.sleep(5);report['quiet_seconds']=time.perf_counter()-quiet
        pulse(xi.set_levels,index);report['stop_api_success']=True
        owner.verify(reader,before,report)
        if not report['configuration_unchanged']:raise ValueError('Configuration readback differs')
        report['status']='PASSED_CUSTOM_EXIT_NATIVE_RECOVERY_CONFIG_PENDING_HUMAN'
    except BaseException as e:report['error']=repr(e)
    finally:
        if timer:timer.close()
        if reader:reader.close()
        if owner:owner.safe.ro.lib.hid_exit()
        out=ROOT/'docs'/('UPDATED_CONFIG_CUSTOM_EXIT_AMP9_'+stamp+'.json');out.write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2));print(out)
    return 0 if report['status'].startswith('PASSED_') else 1
if __name__=='__main__':raise SystemExit(main())
