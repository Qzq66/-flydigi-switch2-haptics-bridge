"""PC-only Flash startup probe. No Flydigi handle, waveform, or USB mode command."""
import argparse,datetime,json,pathlib,struct,subprocess,sys,time
from v043_installation import ROOT,PRIVATE,verify_installed,sha
from pico_v043_probe import Probe
sys.path.insert(0,str(ROOT/'handoff/2026-10-22/work'))
from pico_continuous_log import decode_slots
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--picotool',type=pathlib.Path,required=True);p.add_argument('--pico-serial',required=True);a=p.parse_args()
stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S');report=dict(status='INCOMPLETE',flydigi_access=False,physical_output=False,flash_program_write=False,usb_mode_commands=0,samples=[])
probe=None;start=None
def tool(args,timeout=40):
    with (PRIVATE/('v043-flash-startup-'+stamp+'.txt')).open('a',encoding='utf-8') as h:
        r=subprocess.run([str(a.picotool),*map(str,args),'--ser',a.pico_serial],stdout=h,stderr=subprocess.STDOUT,timeout=timeout)
    if r.returncode:raise ValueError('picotool operation failed; private console retained')
try:
    selection=json.loads((PRIVATE/'v043-install-selection.json').read_text(encoding='utf-8'))
    record=json.loads(pathlib.Path(selection['record']).read_text(encoding='utf-8'))
    report['preflight']=verify_installed(selection['record'],a.picotool,a.pico_serial)
    tool(['reboot']);start=time.monotonic();probe=Probe();probe.open(profile='flash');report['exact_flash_identity']=True
    endpoint=probe.endpoint(timeout=40);report['wifi_up']=True
    secret=json.loads((PRIVATE/'rollback-selection.json').read_text(encoding='utf-8'))
    session=json.loads((pathlib.Path(secret['root'])/'work/private/bridge-session.json').read_text(encoding='utf-8-sig'))
    report['matching_session']=endpoint['session']==int(session['session'],16)
    import importlib.util
    spec=importlib.util.spec_from_file_location('discovery',ROOT/'handoff/2026-10-22/work/bridge-switch-live.py');live=importlib.util.module_from_spec(spec);spec.loader.exec_module(live)
    report['broadcast_matches']=live.discover(endpoint['session'],5)==endpoint['ip']
    next_mark=30
    while time.monotonic()-start<170:
        elapsed=time.monotonic()-start
        if elapsed>=next_mark:
            d=probe.m.read_range(0x9200,104)
            sample=dict(elapsed_seconds=round(elapsed,1),initialized=d[5],active=d[6],enabled=d[7],link_status=struct.unpack_from('<i',d,36)[0],requests=struct.unpack_from('<I',d,24)[0])
            report['samples'].append(sample);print(json.dumps(sample),flush=True);next_mark+=30
        time.sleep(.25)
except BaseException as exc:report['error']=str(exc).replace(a.pico_serial,'[private board]')
finally:
    if probe:
        try:probe.close()
        except BaseException as exc:report['close_error']=type(exc).__name__
    if start is not None:
        # Leave the Flash firmware's existing 180s cap to return to BOOTSEL.
        while time.monotonic()-start<185:time.sleep(.25)
        try:
            raw=PRIVATE/('v043-startup-full-'+stamp+'.bin');tool(['save','-v','-r','0x10000000','0x10400000','-t','bin',raw])
            data=raw.read_bytes();prior=pathlib.Path(record['installed_snapshot']).read_bytes();capture=decode_slots(data[0xe0000:0x100000])
            report.update(capture=capture['newest'],full_flash_sha256=sha(raw),outside_journal_unchanged=data[:0xe0000]==prior[:0xe0000] and data[0x100000:]==prior[0x100000:])
            newest=capture['newest']
            if not report.get('error') and report.get('broadcast_matches') and report.get('matching_session') and report['outside_journal_unchanged'] and newest['generation']==11 and newest['reason']=='boot_limit' and newest['crc_valid'] and newest['complete']:
                report['status']='PASSED_V043_PC_FLASH_STARTUP_BOOT_LIMIT'
        except BaseException as exc:report['readback_error']=str(exc).replace(a.pico_serial,'[private board]')
    out=ROOT/'docs'/('V043_PC_FLASH_STARTUP_'+stamp+'.json');out.write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in report.items() if k!='capture'},indent=2));print(str(out))
raise SystemExit(0 if report['status']=='PASSED_V043_PC_FLASH_STARTUP_BOOT_LIMIT' else 1)
