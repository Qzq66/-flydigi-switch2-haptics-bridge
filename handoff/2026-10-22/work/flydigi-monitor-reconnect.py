"""Read-only physical receiver removal/reinsert observation and config recheck."""
import datetime
import importlib.util
import json
import pathlib
import sys
import time

HERE=pathlib.Path(__file__).parent
spec=importlib.util.spec_from_file_location('safe',HERE/'flydigi-safe-waveform.py')
safe=importlib.util.module_from_spec(spec)
spec.loader.exec_module(safe)

def present_count():
    head=safe.ro.lib.hid_enumerate(0x37D7,0x2502)
    count=0
    try:
        node=head
        while node:
            entry=node.contents
            if entry.usage_page==0xFFA0 and entry.interface_number==2:count+=1
            node=entry.next
    finally:
        if head:safe.ro.lib.hid_free_enumeration(head)
    return count

def main():
    backup_path=pathlib.Path(sys.argv[1])
    backup=json.loads(backup_path.read_text(encoding='utf-8'))
    report=dict(configuration_write_commands=0,streaming_frames=0,backup_file=backup_path.name,events=[])
    reader=None
    safe.ro.lib.hid_init()
    try:
        if present_count()!=1:raise ValueError('Expected one connected baseline interface')
        print('READY: waiting for receiver unplug and reinsert; output is stopped.',flush=True)
        report['baseline_present']=True
        missing=0
        disconnected=False
        deadline=time.monotonic()+100
        while time.monotonic()<deadline:
            count=present_count()
            if count==0:
                missing+=1
                if missing>=3 and not disconnected:
                    disconnected=True
                    report['events'].append(dict(event='USB_VENDOR_INTERFACE_ABSENT',time=datetime.datetime.now().astimezone().isoformat()))
                    print('DISCONNECTED observed',flush=True)
            else:
                missing=0
                if disconnected and count==1:
                    report['events'].append(dict(event='USB_VENDOR_INTERFACE_REAPPEARED',time=datetime.datetime.now().astimezone().isoformat()))
                    print('RECONNECTED observed; reading identity/configuration only',flush=True)
                    time.sleep(0.6)
                    break
                if count>1:raise ValueError('Multiple receivers appeared; refusing selection')
            time.sleep(0.2)
        else:raise TimeoutError('Physical unplug/reinsert was not observed within 100 seconds')
        reader=safe.open_reader(report)
        uid=reader.ask(4,reply_size=16)
        report['identity_matches']=safe.digest(uid)==backup['device']['identity_sha256']
        if not report['identity_matches']:raise ValueError('Different controller after reconnect')
        report['state_matches']=list(reader.state())==backup['state_before']
        report['ram_matches']={}
        for name,entry in backup['ram'].items():
            data,_=safe.read_ram(reader,entry['ram_id'])
            report['ram_matches'][name]=data.hex()==entry['raw_hex']
        report['status']='RECONNECT_AND_CONFIG_RECHECK_PASSED' if report['state_matches'] and all(report['ram_matches'].values()) and len(report['ram_matches'])==4 else 'CONFIG_MISMATCH'
        report['automatic_output_resume']=False
    except BaseException as exc:
        report['status']='STOPPED_OR_INCOMPLETE'
        report['error']=f'{type(exc).__name__}: {exc}'
    finally:
        if reader:reader.close()
        safe.ro.lib.hid_exit()
        path=safe.ro.ROOT/'outputs'/'flydigi-receiver-reconnect.json'
        path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':main()
