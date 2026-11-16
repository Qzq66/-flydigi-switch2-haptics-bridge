"""One manual120ms pulse with complete before/after read evidence; Pico untouched."""
import pathlib,sys,json,time,datetime,math,hashlib
from config_output_trace import VolatileOutputTrace
from config_read_trace import compare_bytes,assess_reads
ROOT=pathlib.Path(__file__).absolute().parents[1];PRIVATE=ROOT/'handoff/2026-10-22/work/private'
def short_pulse(reader,safe,stop,clock=time.perf_counter,pause=time.sleep):
    frames=0
    try:
        reader.mode(bytes.fromhex('0112024000'));target=clock()
        for block in range(15):
            if clock()-target>.004:raise RuntimeError('Dispatch late; no catch-up')
            values=[128+round(9*math.sin(2*math.pi*160*(block*8+i)/1000)) for i in range(8)]
            reader.stream(safe.waveform(values,values,maximum_offset=9));frames+=1;target+=.008;pause(max(0.,target-clock()))
        return frames
    finally:stop()

def main():
    from startup_current_config_owner import load_owner
    from bridge_windows import XInputSource,TimerResolution
    from bridge_input import NEUTRAL
    import tkinter as tk
    stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S');owner=load_owner();original=owner.safe.ro.lib;trace=VolatileOutputTrace(original);owner.safe.ro.lib=trace
    reader=timer=None;dirty=False;raw_rows=[];pre=[];post=[]
    report=dict(status='INCOMPLETE',manual_clicked=False,configuration_writes=0,pico_access=False,custom_hz=160,peak_offset=9,source_ms=120)
    def capture(label):
        started=time.perf_counter();begin=len(trace.events);state=list(reader.state());regions={};raw={}
        for rid,name in ((1,'global'),(4,'mapping'),(5,'lighting'),(6,'motors')):
            data,summary=owner.safe.read_ram(reader,rid);raw[name]=dict(raw_hex=data.hex(),**summary);regions[name]=compare_bytes(bytes.fromhex(expected['ram'][name]['raw_hex']),data)
        after=list(reader.state());end=time.perf_counter();raw_rows.append(dict(label=label,state_before=state,state_after=after,ram=raw))
        return dict(label=label,start=started,end=end,trace_begin=begin,trace_end=len(trace.events),state_matches=state==after==expected['state'],comparisons=regions)
    try:
        selection=json.loads((PRIVATE/'startup-config-selection-2026-11-15.json').read_text());snapshot=pathlib.Path(selection['current_configuration_backup'])
        if hashlib.sha256(snapshot.read_bytes()).hexdigest()!=selection['sha256']:raise ValueError('Expected snapshot changed')
        expected=json.loads(snapshot.read_text());reader=owner.safe.open_reader({})
        if owner.safe.digest(reader.ask(4,reply_size=16))!=expected['identity_sha256']:raise ValueError('Identity mismatch')
        for i in range(3):
            pre.append(capture('before-'+str(i)));time.sleep(.2)
        if not assess_reads(pre)['all_samples_match'] or not all(r['state_matches'] for r in pre):raise ValueError('Baseline not stable; no output')
        source=XInputSource()
        if source()!=NEUTRAL:raise ValueError('Release all controls before start')
        root=tk.Tk();root.title('Read evidence: one short pulse');root.geometry('650x260');root.attributes('-topmost',True);ready=[False]
        label=tk.Label(root,text='One160Hz +/-9 pulse120ms; then read-only checks.\nPico stays BOOTSEL. Click START, hold both grips;6second countdown.\nNo persistent configuration writes.',wraplength=600);label.pack(pady=20)
        def countdown(n):
            label.configure(text='Prepare both grips: '+str(n))
            if n:root.after(1000,lambda:countdown(n-1))
            else:ready[0]=True;root.destroy()
        def click():report['manual_clicked']=True;button.configure(state='disabled');countdown(6)
        button=tk.Button(root,text='START ONE SHORT PULSE',command=click);button.pack();root.after(90000,root.destroy);root.mainloop()
        if not ready[0]:raise ValueError('Cancelled before pulse')
        if source()!=NEUTRAL:raise ValueError('Controls not neutral; no output')
        # Close the manual wait gap with an exact fresh snapshot.
        pre.append(capture('immediately-before'))
        if not assess_reads(pre)['all_samples_match'] or not pre[-1]['state_matches']:raise ValueError('Configuration changed while waiting; no output')
        timer=TimerResolution()
        if not timer.start():raise RuntimeError('Timer acquisition failed')
        reader.allowed_modes=owner.MODES;reader.maximum_offset=9;dirty=True
        report['frames']=short_pulse(reader,owner.safe,lambda:owner.stop(reader,report))
        dirty=False;report['stop_confirmed_at']=time.perf_counter()
        for i in range(5):
            if i:time.sleep(.2)
            post.append(capture('after-'+str(i)))
        report.update(before=pre,after=post,assessment=assess_reads(post))
        if report['assessment']['all_samples_match'] and all(r['state_matches'] for r in post):report['status']='PASSED_SHORT_PULSE_READ_COMPARISON_PENDING_HUMAN'
    except BaseException as exc:report['error']=repr(exc)
    finally:
        # Trace capacity or instrumentation errors must never prevent cleanup.
        if dirty and reader:
            owner.safe.ro.lib=original
            try:owner.stop(reader,report)
            except BaseException as exc:report['cleanup_error']=repr(exc)
        if timer:timer.close()
        if reader:reader.close()
        owner.safe.ro.lib=original;original.hid_exit()
        rawpath=PRIVATE/('config-stop-trace-raw-'+stamp+'.json');rawpath.write_text(json.dumps(dict(trace_events=trace.events,snapshots=raw_rows),indent=2),encoding='utf-8')
        report.update(before=pre,after=post,trace_events=len(trace.events),raw_bytes=trace.raw_bytes,raw_evidence_sha256=hashlib.sha256(rawpath.read_bytes()).hexdigest())
        out=ROOT/'docs'/('CONFIG_STOP_TRACE_'+stamp+'.json');out.write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in report.items() if k not in ('before','after')},indent=2));print(out)
    return 0 if report['status'].startswith('PASSED') else 1
if __name__=='__main__':raise SystemExit(main())
