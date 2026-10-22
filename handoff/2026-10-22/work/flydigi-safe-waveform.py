"""Bounded volatile grip test: backup first, neutral/group-disable in finally.

Never issues save, flash write, firmware upgrade, factory reset or slot selection.
Protocol facts: openflydigi gpa6.py/waveform.py at 11653507bbe4dc77f3c479c2a7aaebf25bbda995.
"""
import argparse
import ctypes as C
import datetime
import hashlib
import json
import math
import pathlib
import struct
import sys
import time
import zlib

import importlib.util
_spec=importlib.util.spec_from_file_location('readonly',pathlib.Path(__file__).with_name('flydigi-readonly.py'))
ro=importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ro)

def digest(data): return hashlib.sha256(data).hexdigest()

def packet(command,payload):
    if len(payload)>27: raise ValueError('Payload too long')
    frame=bytearray(32)
    frame[:4]=bytes((0x5a,0xa5,command,len(payload)+2))
    frame[4:4+len(payload)]=payload
    frame[31]=sum(frame[2:31])&255
    return bytes((0,))+frame

def waveform(left=None,right=None,off=False,maximum_offset=5):
    left=[128]*8 if left is None else left
    right=[128]*8 if right is None else right
    if len(left)!=8 or len(right)!=8: raise ValueError('Exactly eight samples required')
    if not isinstance(maximum_offset,int) or not 1<=maximum_offset<=12:raise ValueError('Unsupported waveform bound')
    if any(not isinstance(x,int) or abs(x-128)>maximum_offset for x in left+right):
        raise ValueError('Amplitude exceeds explicit 8-bit sample-code bound')
    payload=bytearray((0x80 if off else 0x98,))
    for l,r in zip(left,right): payload.extend((128,l,r))
    return packet(0x57,payload)

class TestReader(ro.Reader):
    def __init__(self,path,output_bytes):
        super().__init__(path,output_bytes)
        self.allowed_modes=set()
        self.stream_frames=0
        self.maximum_offset=5
    def validate_query(self,command,payload):
        if command==0x53:
            if payload not in self.allowed_modes: raise ValueError('Unapproved volatile motor payload')
        else: super().validate_query(command,payload)
    def ask(self,command,payload=b'',*,reply_size,modern=False):
        # Only idempotent reads may be retried here; settings use their own policy.
        attempts=3 if command in ro.Reader.ALLOWED else 1
        for attempt in range(attempts):
            try:return super().ask(command,payload,reply_size=reply_size,modern=modern)
            except TimeoutError:
                if attempt+1==attempts:raise
                time.sleep(0.08)
    def mode(self,payload):
        status=self.ask(0x53,payload,reply_size=1)[0]
        if status: raise ValueError(f'Runtime motor command refused: {status}')
    def stream(self,report):
        if len(report)!=33 or report[1:5]!=b'\x5a\xa5\x57\x1b':
            raise ValueError('Not an approved waveform frame')
        if report[5] not in (0x98,0x80): raise ValueError('Trigger or unknown selector refused')
        if report[32] != sum(report[3:32])&255: raise ValueError('Checksum mismatch')
        if not isinstance(self.maximum_offset,int) or not 1<=self.maximum_offset<=12:raise ValueError('Unsupported reader amplitude bound')
        for i in range(8):
            pos=6+3*i
            if report[pos]!=128 or abs(report[pos+1]-128)>self.maximum_offset or abs(report[pos+2]-128)>self.maximum_offset:
                raise ValueError('Unsafe channel/sample')
        if report[30:32]!=b'\0\0': raise ValueError('Unexpected padding')
        tx=C.create_string_buffer(report,len(report))
        if ro.lib.hid_write(self.handle,tx,len(report))!=len(report): raise OSError('Waveform HID write failed')
        self.stream_frames+=1

def ram_info(reader,ram_id):
    p=reader.ask(0xA3,bytes((1,ram_id)),reply_size=10,modern=True)
    if p[:3]!=bytes((1,0,ram_id)) or p[3]>3: raise ValueError('Invalid RAM query')
    return struct.unpack('<BHI',p[3:])

def read_ram(reader,ram_id):
    before=ram_info(reader,ram_id)
    slot,total,crc=before
    if total>4096: raise ValueError('RAM too large for proven read protocol')
    data=bytearray()
    for index in range((total+15)//16):
        p=reader.ask(0xA3,bytes((0,ram_id,index,16)),reply_size=lambda p:8+p[7],modern=True)
        wanted=min(16,total-len(data))
        if p[:7]!=struct.pack('<4BHB',0,0,ram_id,slot,total,index) or p[7] not in (wanted,16):
            raise ValueError('RAM chunk mismatch')
        data.extend(p[8:8+wanted])
    if ram_info(reader,ram_id)!=before or zlib.crc32(data)!=crc: raise ValueError('RAM consistency check failed')
    return bytes(data),dict(active_slot=slot,bytes=total,crc32=f'{crc:08X}',sha256=digest(data))

def open_reader(report):
    ro.lib.hid_init()
    head=ro.lib.hid_enumerate(0x37D7,0x2502)
    candidates=[]
    try:
        node=head
        while node:
            d=node.contents
            if d.usage_page==0xFFA0 and d.interface_number==2:
                candidates.append((bytes(d.path),ro.descriptor_caps(d.path)))
            node=d.next
    finally:
        if head: ro.lib.hid_free_enumeration(head)
    if len(candidates)!=1: raise ValueError('Exactly one known FFA0/MI02 interface is required')
    path,caps=candidates[0]
    if caps['input_bytes']!=33 or caps['output_bytes']!=33: raise ValueError('Unexpected HID report lengths')
    report['interface']=dict(vid='37D7',pid='2502',usage_page='FFA0',interface=2,**caps)
    return TestReader(path,33)

def self_test():
    neutral=waveform()
    assert neutral[5]==0x98 and neutral[6:30]==bytes((128,128,128))*8
    assert neutral[32]==sum(neutral[3:32])&255
    left=waveform([123,124,125,126,129,130,132,133])
    assert all(left[8+3*i]==128 for i in range(8))
    assert waveform(off=True)[5]==0x80
    try: waveform([134]*8)
    except ValueError: pass
    else: raise AssertionError('Amplitude cap missing')

def disable_runtime(reader, *, attempts=3, settle_seconds=0.08, sleep=time.sleep):
    """Idempotent group-disable only. Retry missing/transport ACKs, not rejection.

    Never falls back to profile saves or guessed per-grip mode parameters.
    """
    if not 1<=attempts<=3:raise ValueError('Shutdown retry bound exceeded')
    events=[]
    sleep(settle_seconds)
    for attempt in range(1,attempts+1):
        try:
            reader.mode(b'\x01\x12\x00')
            events.append(dict(attempt=attempt,status='ACK_OK'))
            return events
        except (TimeoutError,OSError) as exc:
            events.append(dict(attempt=attempt,status=type(exc).__name__))
            if attempt==attempts:raise RuntimeError('Runtime disable not acknowledged within retry bound') from exc
            sleep(settle_seconds)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--play',action='store_true',help='Enable bounded volatile output after backup')
    pair_group=parser.add_mutually_exclusive_group()
    pair_group.add_argument('--frequency-pair',action='store_true',help='Two same-side 80/160 Hz 600 ms tones, unchanged amplitude')
    pair_group.add_argument('--wide-frequency-pair',action='store_true',help='Two same-side 60/240 Hz 600 ms tones, unchanged amplitude')
    args=parser.parse_args()
    self_test()
    stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    output=ro.ROOT/'outputs'
    report=dict(started_at=datetime.datetime.now().astimezone().isoformat(),persistent_write_commands=0,
                save_commands=0,reset_commands=0,slot_change_commands=0,trigger_samples='neutral only',
                maximum_sample_offset=5,full_scale_offset=127,phases=[],cleanup=[],status='STARTING')
    reader=None
    saved={}
    before=None
    uid=None
    dirty=False
    timer=False
    main_error=None
    try:
        reader=open_reader(report)
        info=reader.ask(1,reply_size=25)
        if info[0] not in (0x96,0x98) or not info[24]&0x80: raise ValueError('No recognized Pro grip-haptic capability')
        uid=reader.ask(4,reply_size=16)
        report['device']=dict(type=f'{info[0]:02X}',features=f'{info[24]:02X}',identity_sha256=digest(uid))
        before=reader.state()
        report['state_before']=before
        backup=dict(created_at=report['started_at'],scope='Global RAM and ACTIVE slot mapping/lighting/motor RAM only; not all stored slots',device=report['device'],state_before=before,ram={})
        for ram_id,name in ((1,'global'),(4,'mapping'),(5,'lighting'),(6,'motors')):
            data,summary=read_ram(reader,ram_id)
            saved[ram_id]=(data,summary)
            backup['ram'][name]=dict(ram_id=ram_id,**summary,raw_hex=data.hex())
        if reader.state()!=before or reader.ask(4,reply_size=16)!=uid: raise ValueError('Device/profile changed during backup')
        for ram_id,(_,summary) in saved.items():
            if ram_info(reader,ram_id)!=(summary['active_slot'],summary['bytes'],int(summary['crc32'],16)):
                raise ValueError('Configuration changed during backup')
        motor=saved[6][0]
        if len(motor)!=64 or motor[0]!=2: raise ValueError('Unknown motor layout; no changes allowed')
        backup['grip_modes_before']=[motor[23],motor[25]]
        backup['exit_policy']='neutral, channels off, acknowledged group runtime disable; no per-grip writes'
        if args.play:
            proof=json.loads((output/'flydigi-runtime-exit-validation.json').read_text(encoding='utf-8'))
            if not proof.get('human_before_and_after_rumble_confirmed'):
                raise ValueError('No completed native-rumble exit validation')
            if digest(uid)!=proof['identity_sha256'] or digest(motor)!=proof['motor_ram_sha256']:
                raise ValueError('Device or motor settings differ from validated exit case; playback refused')
        backup_path=output/f'flydigi-backup-{stamp}.json'
        with backup_path.open('x',encoding='utf-8') as handle:
            json.dump(backup,handle,ensure_ascii=False,indent=2)
            handle.flush()
        if json.loads(backup_path.read_text(encoding='utf-8'))!=json.loads(json.dumps(backup)):
            raise ValueError('Local backup readback mismatch')
        report['backup_file']=backup_path.name
        report['backup_sha256']=digest(backup_path.read_bytes())
        report['backup_summary']={name:{k:v for k,v in entry.items() if k!='raw_hex'} for name,entry in backup['ram'].items()}
        report['exit_policy']=backup['exit_policy']
        print('Backup complete and verified:',backup_path.name,flush=True)
        if not args.play:
            report['status']='BACKUP_ONLY_PASSED'
        else:
            reader.allowed_modes={b'\x01\x12\x02\x40\x00',b'\x01\x12\x00'}
            report['inter_phase_seconds']=2.0
            stages=(('left',60),('left',240)) if args.wide_frequency_pair else ((('left',80),('left',160)) if args.frequency_pair else (('left',80),('right',80),('left',160),('right',160)))
            block_count=75 if args.frequency_pair or args.wide_frequency_pair else 30
            nominal_ms=block_count*8
            report['test_plan']='same-left-wide-frequency-pair' if args.wide_frequency_pair else ('same-left-frequency-pair' if args.frequency_pair else 'left-right-frequency-sequence')
            print('Starting in 2 seconds: '+', '.join(f'{side}{hz}' for side,hz in stages),flush=True)
            time.sleep(2.0)
            # Mark before sending: an ACK timeout must still invoke restoration.
            dirty=True
            reader.mode(b'\x01\x12\x02\x40\x00')
            timer=C.WinDLL('winmm').timeBeginPeriod(1)==0
            for number,(side,hz) in enumerate(stages,1):
                phase=dict(order=number,side=side,hz=hz,nominal_ms=nominal_ms,frames=0)
                print(f'LOW-AMPLITUDE TEST {side} {hz} Hz, nominal {nominal_ms} ms',flush=True)
                start=time.perf_counter()
                deadline=start
                for block in range(block_count):
                    if time.perf_counter()-start>0.8: raise TimeoutError('Phase wall-time cap reached')
                    values=[]
                    for i in range(8):
                        sample=block*8+i
                        envelope=min(1,sample/20,(nominal_ms-1-sample)/20)
                        values.append(128+round(5*envelope*math.sin(2*math.pi*hz*sample/1000)))
                    reader.stream(waveform(left=values if side=='left' else None,right=values if side=='right' else None))
                    phase['frames']+=1
                    deadline+=0.008
                    gap=deadline-time.perf_counter()
                    if gap>0: time.sleep(gap)
                    if gap < -0.04: raise TimeoutError('Streaming schedule fell behind; stop rather than burst')
                phase['actual_ms']=round((time.perf_counter()-start)*1000,3)
                report['phases'].append(phase)
                # Explicit neutral frames; no continuing source between phases.
                for _ in range(3): reader.stream(waveform()); time.sleep(0.008)
                if number<len(stages):
                    gap_start=time.perf_counter()
                    while time.perf_counter()-gap_start<2.0:
                        reader.stream(waveform())
                        time.sleep(0.04)
            report['status']='STREAM_TEST_COMPLETED_PENDING_RESTORE'
    except BaseException as exc:
        main_error=f'{type(exc).__name__}: {exc}'
        report['error']=main_error
        report['status']='STOPPED'
    finally:
        if reader and dirty:
            try:
                if reader.ask(4,reply_size=16)!=uid: raise ValueError('Device identity changed; restoration refused on replacement')
                for name,frame in (('neutral',waveform()),('channels_off',waveform(off=True))):
                    try: reader.stream(frame); report['cleanup'].append(name+': OK')
                    except BaseException as exc: report['cleanup'].append(name+': '+str(exc))
                report['disable_attempts']=disable_runtime(reader)
                report['cleanup'].append('group runtime disable: ACK OK')
                report['runtime_disable_acknowledged']=True
            except BaseException as exc:
                report['restoration_error']=f'{type(exc).__name__}: {exc}'
                report['status']='RESTORATION_INCOMPLETE'
        if reader and saved and before is not None:
            try:
                report['state_after']=reader.state()
                report['state_unchanged']=tuple(report['state_after'])==before
                report['ram_equal_after']={}
                for ram_id,name in ((1,'global'),(4,'mapping'),(5,'lighting'),(6,'motors')):
                    if ram_id not in saved: continue
                    current,summary=read_ram(reader,ram_id)
                    report['ram_equal_after'][name]=current==saved[ram_id][0]
                report['identity_unchanged']=reader.ask(4,reply_size=16)==uid
                equal=(report['state_unchanged'] and all(report['ram_equal_after'].values()) and len(report['ram_equal_after'])==4 and report['identity_unchanged'])
                report['configuration_unchanged']=equal if len(report['ram_equal_after'])==4 else None
                if dirty and not report.get('restoration_error') and equal and not main_error:
                    report['status']='PASSED_STREAM_STOP_AND_CONFIG_RECHECK'
                elif len(report['ram_equal_after'])!=4:report['status']='RECHECK_INCOMPLETE'
                elif not equal: report['status']='CONFIGURATION_RECHECK_FAILED'
            except BaseException as exc:
                report['verification_error']=f'{type(exc).__name__}: {exc}'
                report['status']='RECHECK_INCOMPLETE'
        if timer: C.WinDLL('winmm').timeEndPeriod(1)
        if reader:
            report['command_counts']=reader.query_counts
            report['stream_frames']=reader.stream_frames
            reader.close()
        ro.lib.hid_exit()
        report['ended_at']=datetime.datetime.now().astimezone().isoformat()
        report_path=output/f'flydigi-waveform-{stamp}.json'
        report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
    return 0 if report['status'] in ('BACKUP_ONLY_PASSED','PASSED_STREAM_STOP_AND_CONFIG_RECHECK') else 1

if __name__=='__main__': sys.exit(main())
