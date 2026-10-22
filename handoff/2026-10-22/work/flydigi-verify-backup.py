"""Verify the current active configuration against an existing backup; no writes."""
import importlib.util
import json
import pathlib
import sys

spec=importlib.util.spec_from_file_location('safe',pathlib.Path(__file__).with_name('flydigi-safe-waveform.py'))
safe=importlib.util.module_from_spec(spec)
spec.loader.exec_module(safe)

def main():
    backup_path=pathlib.Path(sys.argv[1])
    backup=json.loads(backup_path.read_text(encoding='utf-8'))
    report=dict(configuration_write_commands=0,backup_file=backup_path.name)
    reader=None
    try:
        reader=safe.open_reader(report)
        uid=reader.ask(4,reply_size=16)
        report['identity_matches']=safe.digest(uid)==backup['device']['identity_sha256']
        if not report['identity_matches']: raise ValueError('Different device; no further queries')
        report['state_matches']=list(reader.state())==backup['state_before']
        report['ram_matches']={}
        for name,entry in backup['ram'].items():
            data,summary=safe.read_ram(reader,entry['ram_id'])
            report['ram_matches'][name]=data.hex()==entry['raw_hex']
        report['status']='MATCH' if report['state_matches'] and all(report['ram_matches'].values()) else 'MISMATCH'
    except Exception as exc:
        report['status']='STOPPED'
        report['error']=f'{type(exc).__name__}: {exc}'
    finally:
        if reader:reader.close()
        safe.ro.lib.hid_exit()
        path=safe.ro.ROOT/'outputs'/'flydigi-config-recheck.json'
        path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0 if report['status']=='MATCH' else 1

if __name__=='__main__':sys.exit(main())
