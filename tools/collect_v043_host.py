"""Read back BOOTSEL Flash after a host test; never load or start firmware."""
import argparse,datetime,json,pathlib,subprocess,sys
from v043_installation import ROOT,PRIVATE,sha
sys.path.insert(0,str(ROOT/'handoff/2026-10-22/work'))
from pico_continuous_log import decode_slots
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--picotool',type=pathlib.Path,required=True);p.add_argument('--pico-serial',required=True);a=p.parse_args()
stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S');raw=PRIVATE/('v043-host-full-'+stamp+'.bin')
report=dict(status='INCOMPLETE',flash_write=False,flydigi_commands=0,checks={})
def require(name,condition):
    report['checks'][name]=bool(condition)
    if not condition:raise ValueError(name)
try:
    selection=json.loads((PRIVATE/'v043-install-selection.json').read_text(encoding='utf-8'))
    installed=json.loads(pathlib.Path(selection['record']).read_text(encoding='utf-8'))
    require('same_board',installed['pico_serial']==a.pico_serial)
    before=pathlib.Path(installed['installed_snapshot']);image=pathlib.Path(installed['image'])
    require('private_material_unchanged',sha(before)==installed['installed_snapshot_sha256'] and sha(image)==installed['firmware_sha256'])
    with (PRIVATE/('v043-readback-'+stamp+'.txt')).open('w',encoding='utf-8') as console:
        result=subprocess.run([str(a.picotool),'save','-v','-r','0x10000000','0x10400000','-t','bin',str(raw),'--ser',a.pico_serial],stdout=console,stderr=subprocess.STDOUT,timeout=40)
    require('full_readback_verified',result.returncode==0 and raw.stat().st_size==4194304)
    data=raw.read_bytes();prior=before.read_bytes();end=int(installed['program_erase_end'],16)
    require('candidate_program_unchanged',data[:len(image.read_bytes())]==image.read_bytes())
    require('outside_journal_unchanged',data[:0xe0000]==prior[:0xe0000] and data[0x100000:]==prior[0x100000:])
    decoded=decode_slots(data[0xe0000:0x100000]);baseline=decode_slots(prior[0xe0000:0x100000])['newest']
    newest=decoded['newest'];old_slot=baseline['slot_index'];offset=0xe0000+old_slot*65536
    report.update(newest=newest,slots=decoded['slots'],full_flash_sha256=sha(raw),firmware_sha256=installed['firmware_sha256'])
    require('previous_generation_preserved',data[offset:offset+65536]==prior[offset:offset+65536])
    require('fresh_single_generation',((newest['generation']-baseline['generation'])&0xffffffff)==1)
    require('complete_persistent_journal',newest['complete'] and newest['crc_valid'] and newest['no_flash_marker']==0)
    report.update(status='V043_HOST_FLASH_READBACK_VERIFIED',newest=newest,slots=decoded['slots'],full_flash_sha256=sha(raw),firmware_sha256=installed['firmware_sha256'])
except BaseException as exc:report['error']=str(exc).replace(a.pico_serial,'[private board]')
finally:
    output=ROOT/'docs'/('V043_HOST_CAPTURE_'+stamp+'.json');output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('newest','slots')},indent=2));print(str(output))
raise SystemExit(0 if report['status']=='V043_HOST_FLASH_READBACK_VERIFIED' else 1)
