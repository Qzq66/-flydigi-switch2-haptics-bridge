"""A/B check of native rumble before/after a neutral realtime session.

Only two approved volatile configurations are permitted: enable neutral grip
streaming and disable it. Does not use per-grip restore or persistent commands.
"""
import ctypes as C
import datetime
import importlib.util
import json
import pathlib
import time

HERE=pathlib.Path(__file__).parent
def module(name,file):
    spec=importlib.util.spec_from_file_location(name,HERE/file)
    result=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result
safe=module('safe','flydigi-safe-waveform.py')
xi=module('xi','flydigi-xinput.py')

def main():
    stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    result=dict(started_at=datetime.datetime.now().astimezone().isoformat(),persistent_write_commands=0,
                per_grip_restore_commands=0,non_neutral_custom_waveform_frames=0,rumble_phases=[])
    reader=None
    index=None
    dirty=False
    original=None
    uid=None
    saved={}
    try:
        safe.self_test()
        reader=safe.open_reader(result)
        info=reader.ask(1,reply_size=25)
        if info[0] not in (0x96,0x98) or not info[24]&0x80:raise ValueError('Unexpected device capability')
        uid=reader.ask(4,reply_size=16)
        original=reader.state()
        index=xi.flydigi_index()
        result['xinput_slot']=index
        result['identity_sha256']=safe.digest(uid)
        backup=dict(scope='global plus active slot mapping/lighting/motors',state_before=original,
                    identity_sha256=result['identity_sha256'],ram={})
        for ram_id,name in ((1,'global'),(4,'mapping'),(5,'lighting'),(6,'motors')):
            data,summary=safe.read_ram(reader,ram_id)
            saved[ram_id]=(name,data,summary)
            backup['ram'][name]=dict(ram_id=ram_id,**summary,raw_hex=data.hex())
        if reader.state()!=original or reader.ask(4,reply_size=16)!=uid:raise ValueError('State changed during backup')
        backup_file=safe.ro.ROOT/'outputs'/f'flydigi-runtime-backup-{stamp}.json'
        with backup_file.open('x',encoding='utf-8') as f:json.dump(backup,f,ensure_ascii=False,indent=2)
        result['backup_file']=backup_file.name
        if json.loads(backup_file.read_text(encoding='utf-8'))!=json.loads(json.dumps(backup)):
            raise ValueError('Backup readback failed')
        def pulse(label):
            print(label+': normal XInput rumble, 4096/65535 for 180 ms',flush=True)
            start=time.perf_counter()
            try:
                xi.set_levels(index,4096,4096)
                time.sleep(0.18)
            finally:xi.set_levels(index,0,0)
            result['rumble_phases'].append(dict(label=label,xinput_status='OK',nominal_ms=180,actual_ms=round((time.perf_counter()-start)*1000,3)))
        pulse('BEFORE')
        time.sleep(3.0)
        reader.allowed_modes={b'\x01\x12\x02\x40\x00',b'\x01\x12\x00'}
        dirty=True
        reader.mode(b'\x01\x12\x02\x40\x00')
        result['neutral_realtime_enable_ack']=True
        for _ in range(3):reader.stream(safe.waveform());time.sleep(0.008)
        reader.stream(safe.waveform(off=True))
        result['disable_attempts']=safe.disable_runtime(reader)
        dirty=False
        result['realtime_disable_ack']=True
        time.sleep(2.0)
        pulse('AFTER_DISABLE')
        result['status']='TRANSPORT_PASSED_AWAITING_USER_FEEDBACK'
    except BaseException as exc:
        result['error']=f'{type(exc).__name__}: {exc}'
        result['status']='STOPPED'
    finally:
        if index is not None:
            try:xi.set_levels(index,0,0);result['xinput_stop_ok']=True
            except BaseException as exc:result['xinput_stop_error']=str(exc)
        if reader and dirty:
            try:
                if reader.ask(4,reply_size=16)!=uid:raise ValueError('Device identity changed')
                reader.stream(safe.waveform())
                reader.stream(safe.waveform(off=True))
                result['finally_disable_attempts']=safe.disable_runtime(reader)
                result['finally_disable_ack']=True
            except BaseException as exc:result['cleanup_error']=str(exc)
        if reader and saved:
            try:
                result['state_matches']=reader.state()==original
                result['ram_matches']={}
                for ram_id,(name,data,summary) in saved.items():
                    current,_=safe.read_ram(reader,ram_id)
                    result['ram_matches'][name]=data==current
                result['identity_matches']=reader.ask(4,reply_size=16)==uid
                result['configuration_unchanged']=result['state_matches'] and len(result['ram_matches'])==4 and all(result['ram_matches'].values()) and result['identity_matches']
                if not result['configuration_unchanged']:result['status']='CONFIGURATION_MISMATCH'
            except BaseException as exc:
                result['verification_error']=str(exc)
                result['status']='RECHECK_INCOMPLETE'
        if reader:
            result['command_counts']=reader.query_counts
            result['neutral_only_stream_frames']=reader.stream_frames
            reader.close()
        safe.ro.lib.hid_exit()
        result['ended_at']=datetime.datetime.now().astimezone().isoformat()
        report_file=safe.ro.ROOT/'outputs'/f'flydigi-runtime-disable-{stamp}.json'
        report_file.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
