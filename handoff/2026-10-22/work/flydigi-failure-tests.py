"""Bounded source-failure and caught-exception tests, preserving configurations.

The output owner stays alive for producer failures. No claim is made here
about force-killing the owner itself or about unplugging during active output.
"""
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

HERE=pathlib.Path(__file__).parent
def load_safe():
    spec=importlib.util.spec_from_file_location('safe',HERE/'flydigi-safe-waveform.py')
    safe=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(safe)
    return safe

def source(mode):
    C.WinDLL('winmm').timeBeginPeriod(1)
    for block in range(25):
        samples=[128+round(5*math.sin(2*math.pi*80*(block*8+i)/1000)) for i in range(8)]
        print(json.dumps(dict(seq=block,at=time.monotonic(),samples=samples)),flush=True)
        time.sleep(0.008)
    if mode=='source_stall':time.sleep(10)
    # Intentional abrupt producer failure: does not execute producer cleanup.
    import os
    os._exit(23)

def pipe_reader(pipe,inbox):
    try:
        for line in pipe:
            event=json.loads(line)
            try:inbox.put_nowait(event)
            except queue.Full:
                inbox.get_nowait()
                inbox.put_nowait(event)
    finally:inbox.put(None)

class InjectedWorkerFailure(Exception):pass

def run_case(safe,name,stamp):
    report=dict(case=name,persistent_commands=0,watchdog_ms=80,maximum_sample_offset=5,
                frames=0,status='STARTING',cleanup=[])
    reader=None
    producer=None
    dirty=False
    saved={}
    uid=None
    before=None
    stopped_at=None
    last_nonzero=None
    first_output_clock=None
    last_output_clock=None
    expected=False
    try:
        reader=safe.open_reader(report)
        info=reader.ask(1,reply_size=25)
        uid=reader.ask(4,reply_size=16)
        proof=json.loads((safe.ro.ROOT/'outputs'/'flydigi-runtime-exit-validation.json').read_text(encoding='utf-8'))
        if info[0]!=0x96 or safe.digest(uid)!=proof['identity_sha256']:raise ValueError('Unexpected controller')
        before=reader.state()
        backup=dict(case=name,device=dict(identity_sha256=safe.digest(uid)),state_before=before,ram={})
        for ram_id,label in ((1,'global'),(4,'mapping'),(5,'lighting'),(6,'motors')):
            data,summary=safe.read_ram(reader,ram_id)
            saved[ram_id]=(label,data)
            backup['ram'][label]=dict(ram_id=ram_id,**summary,raw_hex=data.hex())
        if safe.digest(saved[6][1])!=proof['motor_ram_sha256']:raise ValueError('Motor configuration differs from validated case')
        if reader.state()!=before or reader.ask(4,reply_size=16)!=uid:raise ValueError('State changed while backing up')
        backup_file=safe.ro.ROOT/'outputs'/f'flydigi-failure-backup-{stamp}-{name}.json'
        with backup_file.open('x',encoding='utf-8') as handle:json.dump(backup,handle,ensure_ascii=False,indent=2)
        if json.loads(backup_file.read_text(encoding='utf-8'))!=json.loads(json.dumps(backup)):raise ValueError('Backup readback failed')
        report['backup_file']=backup_file.name
        reader.allowed_modes={b'\x01\x12\x02\x40\x00',b'\x01\x12\x00'}
        print('TEST '+name+': left grip, about 0.2 seconds, low amplitude',flush=True)
        dirty=True
        reader.mode(b'\x01\x12\x02\x40\x00')
        if name=='worker_exception':
            for block in range(25):
                values=[128+round(5*math.sin(2*math.pi*80*(block*8+i)/1000)) for i in range(8)]
                reader.stream(safe.waveform(left=values))
                last_output_clock=time.perf_counter()
                if first_output_clock is None:first_output_clock=last_output_clock
                report['frames']+=1
                last_nonzero=time.monotonic()
                time.sleep(0.008)
            stopped_at=time.monotonic()
            raise InjectedWorkerFailure('Intentional output-loop exception')
        inbox=queue.Queue(maxsize=4)
        producer=subprocess.Popen([sys.executable,str(pathlib.Path(__file__).resolve()),'--source',name],
                                  stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,bufsize=1,
                                  creationflags=subprocess.CREATE_NO_WINDOW)
        threading.Thread(target=pipe_reader,args=(producer.stdout,inbox),daemon=True).start()
        last_source=time.monotonic()
        deadline=last_source+3
        while time.monotonic()<deadline:
            now=time.monotonic()
            if report['frames'] and now-last_source>=0.08:
                report['stop_reason']='source_watchdog'
                stopped_at=now
                expected=name=='source_stall'
                break
            try:event=inbox.get(timeout=0.008)
            except queue.Empty:continue
            if event is None:
                report['stop_reason']='producer_eof'
                stopped_at=time.monotonic()
                expected=name=='source_crash'
                break
            now=time.monotonic()
            if now-event['at']>=0.08:
                report['stop_reason']='stale_source_packet'
                stopped_at=now
                break
            last_source=event['at']
            reader.stream(safe.waveform(left=event['samples']))
            last_output_clock=time.perf_counter()
            if first_output_clock is None:first_output_clock=last_output_clock
            last_nonzero=time.monotonic()
            report['frames']+=1
        else:raise TimeoutError('Case exceeded three-second safety cap')
    except InjectedWorkerFailure as exc:
        report['stop_reason']='injected_worker_exception'
        report['injected_exception']=str(exc)
        expected=True
    except BaseException as exc:
        report['error']=f'{type(exc).__name__}: {exc}'
    finally:
        if reader and dirty:
            cleanup_start=time.monotonic()
            try:
                reader.stream(safe.waveform())
                neutral_clock=time.perf_counter()
                neutral_at=time.monotonic()
                reader.stream(safe.waveform(off=True))
                report['cleanup'].append('neutral and channels off: OK')
                report['disable_attempts']=safe.disable_runtime(reader)
                report['runtime_disable_ack']=True
                report['cleanup_ms']=round((time.monotonic()-cleanup_start)*1000,3)
                if first_output_clock is not None:
                    report['measured_send_train_ms']=round((last_output_clock-first_output_clock)*1000,3)
                    report['measured_first_send_to_neutral_ms']=round((neutral_clock-first_output_clock)*1000,3)
                if last_nonzero is not None:report['last_nonzero_to_neutral_ms']=round((neutral_at-last_nonzero)*1000,3)
                if stopped_at is not None:report['detection_to_neutral_ms']=round((neutral_at-stopped_at)*1000,3)
            except BaseException as exc:report['cleanup_error']=str(exc)
        if producer:
            if producer.poll() is None:producer.terminate()
            try:producer.wait(timeout=2)
            except subprocess.TimeoutExpired:producer.kill();producer.wait(timeout=2)
            report['producer_exit_code']=producer.returncode
        if reader and saved:
            try:
                report['identity_unchanged']=reader.ask(4,reply_size=16)==uid
                report['state_unchanged']=reader.state()==before
                report['ram_equal']={}
                for ram_id,(label,data) in saved.items():
                    current,_=safe.read_ram(reader,ram_id)
                    report['ram_equal'][label]=current==data
                report['configuration_unchanged']=report['identity_unchanged'] and report['state_unchanged'] and len(report['ram_equal'])==4 and all(report['ram_equal'].values())
            except BaseException as exc:report['recheck_error']=str(exc)
        if reader:
            report['command_counts']=reader.query_counts
            reader.close()
        safe.ro.lib.hid_exit()
        report['status']='PASSED_SOFTWARE_STOP_AND_CONFIG_RECHECK' if expected and report['frames']>=20 and report.get('runtime_disable_ack') and report.get('configuration_unchanged') else 'STOPPED_OR_INCOMPLETE'
    return report

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',choices=('source_stall','source_crash'))
    args=parser.parse_args()
    if args.source:source(args.source);return
    safe=load_safe()
    safe.self_test()
    stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    reports=[]
    timer=C.WinDLL('winmm').timeBeginPeriod(1)==0
    try:
        for name in ('source_stall','source_crash','worker_exception'):
            result=run_case(safe,name,stamp)
            reports.append(result)
            print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
            if result['status']!='PASSED_SOFTWARE_STOP_AND_CONFIG_RECHECK':break
            time.sleep(2)
    finally:
        if timer:C.WinDLL('winmm').timeEndPeriod(1)
    output=safe.ro.ROOT/'outputs'/f'flydigi-failure-tests-{stamp}.json'
    output.write_text(json.dumps(dict(cases=reports,owner_force_kill_tested=False,receiver_hotplug_tested=False),ensure_ascii=False,indent=2),encoding='utf-8')
    print('REPORT '+output.name)
    if len(reports)!=3 or any(r['status']!='PASSED_SOFTWARE_STOP_AND_CONFIG_RECHECK' for r in reports):sys.exit(1)

if __name__=='__main__':main()
