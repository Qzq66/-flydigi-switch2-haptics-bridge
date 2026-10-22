"""Bounded owner termination and active USB loss, without persistent writes."""
import argparse
import ctypes as C
import datetime
import importlib.util
import json
import math
import pathlib
import queue
import subprocess
import sys
import threading
import time

HERE=pathlib.Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('safe',HERE/'flydigi-safe-waveform.py')
safe=importlib.util.module_from_spec(spec)
spec.loader.exec_module(safe)
OUT=safe.ro.ROOT/'outputs'
MODES={b'\x01\x12\x02\x40\x00',b'\x01\x12\x00'}

def present():
    head=safe.ro.lib.hid_enumerate(0x37D7,0x2502)
    count=0
    try:
        node=head
        while node:
            d=node.contents
            if d.usage_page==0xFFA0 and d.interface_number==2:count+=1
            node=d.next
    finally:
        if head:safe.ro.lib.hid_free_enumeration(head)
    return count

def identity(r,b):
    if safe.digest(r.ask(4,reply_size=16))!=b['device']['identity_sha256']:
        raise ValueError('Controller identity mismatch')

def backup(r,path):
    proof=json.loads((OUT/'flydigi-runtime-exit-validation.json').read_text(encoding='utf-8'))
    uid=r.ask(4,reply_size=16)
    info=r.ask(1,reply_size=25)
    if info[0]!=0x96 or safe.digest(uid)!=proof['identity_sha256'] or not proof.get('human_before_and_after_rumble_confirmed'):
        raise ValueError('Not the validated controller')
    b=dict(device=dict(identity_sha256=safe.digest(uid)),state_before=list(r.state()),ram={},scope='Global plus active-slot mapping/lighting/motors only')
    for rid,label in ((1,'global'),(4,'mapping'),(5,'lighting'),(6,'motors')):
        data,summary=safe.read_ram(r,rid)
        b['ram'][label]=dict(ram_id=rid,raw_hex=data.hex(),**summary)
    if b['ram']['motors']['sha256']!=proof['motor_ram_sha256']:raise ValueError('Motor configuration changed')
    identity(r,b)
    if list(r.state())!=b['state_before']:raise ValueError('Slot changed during backup')
    with path.open('x',encoding='utf-8') as h:json.dump(b,h,indent=2)
    if json.loads(path.read_text(encoding='utf-8'))!=b:raise ValueError('Backup readback mismatch')
    return b

def verify(r,b,report):
    identity(r,b)
    report['identity_matches']=True
    report['state_matches']=list(r.state())==b['state_before']
    report['ram_matches']={}
    for label,entry in b['ram'].items():
        data,_=safe.read_ram(r,entry['ram_id'])
        report['ram_matches'][label]=data.hex()==entry['raw_hex']
    report['configuration_unchanged']=report['state_matches'] and len(report['ram_matches'])==4 and all(report['ram_matches'].values())

def stop(r,report):
    r.allowed_modes=MODES
    r.stream(safe.waveform())
    report['neutral_written_clock']=time.perf_counter()
    r.stream(safe.waveform(off=True))
    report['disable_attempts']=safe.disable_runtime(r)
    report['runtime_disable_ack']=True

def samples(block):
    return [128+round(5*math.sin(2*math.pi*80*(block*8+i)/1000)) for i in range(8)]

def child(path):
    b=json.loads(path.read_text(encoding='utf-8'))
    r=None
    dirty=False
    timer=C.WinDLL('winmm').timeBeginPeriod(1)==0
    try:
        r=safe.open_reader({})
        identity(r,b)
        motor,_=safe.read_ram(r,6)
        if motor.hex()!=b['ram']['motors']['raw_hex']:raise ValueError('Motor configuration changed')
        r.allowed_modes=MODES
        dirty=True
        r.mode(b'\x01\x12\x02\x40\x00')
        start=time.perf_counter()
        for block in range(80):
            if time.perf_counter()-start>0.8:break
            r.stream(safe.waveform(left=samples(block)))
            print(json.dumps(dict(frame=block+1,at=time.perf_counter())),flush=True)
            time.sleep(0.008)
    finally:
        if r and dirty:stop(r,{})
        if r:r.close()
        safe.ro.lib.hid_exit()
        if timer:C.WinDLL('winmm').timeEndPeriod(1)

def pipe_events(pipe,inbox):
    try:
        for line in pipe:inbox.put(json.loads(line))
    finally:inbox.put(None)

def run(case):
    stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    report=dict(case=case,persistent_commands=0,maximum_sample_offset=5,automatic_output_resume=False,status='STARTING')
    bp=OUT/f'flydigi-{case}-backup-{stamp}.json'
    path=OUT/f'flydigi-{case}-{stamp}.json'
    r=None
    proc=None
    b=None
    dirty=False
    timer=C.WinDLL('winmm').timeBeginPeriod(1)==0
    try:
        r=safe.open_reader(report)
        b=backup(r,bp)
        report['backup_file']=bp.name
        if case=='owner_kill':
            r.close();r=None
            inbox=queue.Queue()
            proc=subprocess.Popen([sys.executable,str(pathlib.Path(__file__).resolve()),'--child',str(bp)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
            threading.Thread(target=pipe_events,args=(proc.stdout,inbox),daemon=True).start()
            dirty=True
            end=time.perf_counter()+8
            while time.perf_counter()<end:
                try:event=inbox.get(timeout=0.05)
                except queue.Empty:continue
                if event is None:raise RuntimeError('Owner exited before kill point')
                report['last_frame']=event
                if event['frame']>=25:break
            else:raise TimeoutError('Owner ready deadline exceeded')
            proc.kill()
            report['kill_requested_clock']=time.perf_counter()
            proc.wait(timeout=2)
            report['owner_exit_code']=proc.returncode
            report['owner_force_killed']=True
            r=safe.open_reader(report)
            identity(r,b)
            stop(r,report)
            report['kill_to_neutral_ms']=round((report['neutral_written_clock']-report['kill_requested_clock'])*1000,3)
            dirty=False
        else:
            r.allowed_modes=MODES
            print('COUNTDOWN 8 seconds; unplug IMMEDIATELY when vibration begins',flush=True)
            time.sleep(8)
            dirty=True
            r.mode(b'\x01\x12\x02\x40\x00')
            start=time.perf_counter()
            print('ACTIVE: unplug receiver now; maximum six seconds',flush=True)
            report['frames']=0
            for block in range(750):
                if time.perf_counter()-start>=6:break
                try:r.stream(safe.waveform(left=samples(block)))
                except OSError as exc:
                    report['output_write_error']=str(exc)
                    break
                report['frames']+=1
                if block%4==0 and present()==0:break
                time.sleep(0.008)
            report['send_train_ms']=round((time.perf_counter()-start)*1000,3)
            # Confirm actual interface absence, rather than treating any write error as unplug.
            missing_deadline=time.perf_counter()+1
            while time.perf_counter()<missing_deadline and present()!=0:time.sleep(0.05)
            if present()!=0:
                stop(r,report);dirty=False
                raise RuntimeError('No physical disconnect during bounded output; repeat requires a new explicit run')
            report['active_usb_loss_observed']=report['frames']>0
            report['usb_absent_at']=datetime.datetime.now().astimezone().isoformat()
            r.close();r=None
            print('DISCONNECTED: no further playback; waiting for receiver return',flush=True)
            end=time.perf_counter()+90
            while time.perf_counter()<end:
                count=present()
                if count>1:raise ValueError('Multiple receivers; selection refused')
                if count==1:break
                time.sleep(0.1)
            else:raise TimeoutError('Receiver did not return in 90 seconds; runtime cleanup unconfirmed')
            time.sleep(0.4)
            r=safe.open_reader(report)
            identity(r,b)
            stop(r,report)
            dirty=False
            report['usb_returned_at']=datetime.datetime.now().astimezone().isoformat()
        verify(r,b,report)
        injected=report.get('owner_force_killed') if case=='owner_kill' else report.get('active_usb_loss_observed')
        if injected and report.get('runtime_disable_ack') and report.get('configuration_unchanged'):report['status']='PASSED_HOST_RECOVERY_AND_CONFIG_RECHECK'
        else:report['status']='INCOMPLETE'
    except BaseException as exc:
        report['error']=f'{type(exc).__name__}: {exc}'
        report['status']='INCOMPLETE'
    finally:
        if proc and proc.poll() is None:proc.kill();proc.wait(timeout=2)
        if dirty and b:
            try:
                if r is None:r=safe.open_reader(report)
                identity(r,b)
                stop(r,report)
            except BaseException as exc:report['cleanup_error']=str(exc)
        if b and r and not report.get('configuration_unchanged'):
            try:verify(r,b,report)
            except BaseException as exc:report['recheck_error']=str(exc)
        if r:r.close()
        safe.ro.lib.hid_exit()
        if timer:C.WinDLL('winmm').timeEndPeriod(1)
        path.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
        print(json.dumps(report,indent=2,ensure_ascii=False),flush=True)
        print('REPORT '+str(path),flush=True)
    return 0 if report['status']=='PASSED_HOST_RECOVERY_AND_CONFIG_RECHECK' else 1

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--case',choices=('owner_kill','active_hotplug'))
    p.add_argument('--child',type=pathlib.Path)
    a=p.parse_args()
    safe.self_test()
    if a.child:child(a.child);return 0
    if not a.case:p.error('--case is required')
    return run(a.case)

if __name__=='__main__':sys.exit(main())
