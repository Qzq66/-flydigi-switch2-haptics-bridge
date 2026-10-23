"""Install reviewed v043 only from the exact frozen v042 baseline. Leave BOOTSEL."""
import argparse,datetime,json,pathlib,subprocess,sys
from v043_installation import ROOT,PRIVATE,sha
sys.path.insert(0,str(ROOT/'handoff/2026-10-22/work'))
from pico_continuous_log import decode_slots
p=argparse.ArgumentParser(description=__doc__)
for name in ('picotool','image'):p.add_argument('--'+name,type=pathlib.Path,required=True)
p.add_argument('--pico-serial',required=True);p.add_argument('--expected-sha256',required=True);a=p.parse_args()
stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
folder=PRIVATE/('v043-install-'+stamp);folder.mkdir()
report=dict(status='INCOMPLETE',flydigi_commands=0,checks={},started_at=datetime.datetime.now().astimezone().isoformat())
def require(name,condition):
    report['checks'][name]=bool(condition)
    if not condition:raise ValueError(name)
def tool(label,args):
    with (folder/'console.txt').open('a',encoding='utf-8') as console:
        console.write(label+'\n');console.flush()
        r=subprocess.run([str(a.picotool),*map(str,args),'--ser',a.pico_serial],stdout=console,stderr=subprocess.STDOUT,timeout=40)
    require(label,r.returncode==0)
try:
    baseline=PRIVATE/'v042-full-baseline-20261023.bin'
    saved=json.loads((ROOT/'docs/STAGED_GAME_BASELINE_2026-10-23.json').read_text())
    require('complete_frozen_baseline',baseline.stat().st_size==4194304 and sha(baseline)==saved['current_full_flash_sha256'])
    recovery=json.loads((PRIVATE/'v042-pre-flash-selection.json').read_text(encoding='utf-8-sig'))
    require('original_recovery_verified',recovery['original_recovery_verified'] is True)
    manifest=json.loads(a.image.with_suffix('.manifest.json').read_text())
    blob=a.image.read_bytes();digest=sha(a.image);end=(len(blob)+4095)//4096*4096
    require('reviewed_image',digest==a.expected_sha256.lower()==manifest['sha256'])
    require('flash_bounds',manifest['profile']=='flash' and manifest['bytes']==len(blob) and 0<len(blob)<=end<=0xe0000 and int(manifest['program_erase_end'],16)==end)
    cache=(a.image.parent/'CMakeCache.txt').read_text(encoding='utf-8')
    require('actual_flash_profile', 'PICO_NO_FLASH:BOOL=0' in cache and 'BRIDGE_RAM_DIAGNOSTIC_RECOVERY:BOOL=OFF' in cache)
    require('candidate_identity',b'Bridge Pro Live 043\0' in blob and b'BPCAP-RP2350-LOCAL-043\0' in blob)
    require('steam_exited',subprocess.run(['powershell.exe','-NoProfile','-Command','if(Get-Process steam -ErrorAction SilentlyContinue){exit 1}'],capture_output=True).returncode==0)
    tool('current_full_baseline_verified',['verify',baseline,'-t','bin','-o','0x10000000'])
    suffix=folder/'preserved-tail.bin';suffix.write_bytes(baseline.read_bytes()[end:])
    capture=decode_slots(baseline.read_bytes()[0xe0000:0x100000])['newest']
    require('expected_generation_10',capture['generation']==10 and capture['complete'] and capture['crc_valid'])
    report.update(firmware_sha256=digest,program_bytes=len(blob),program_erase_end=hex(end),baseline_generation=10,backup_sha256=sha(baseline))
    tool('candidate_program_loaded_and_verified',['load','-v',a.image,'-t','bin','-o','0x10000000'])
    tool('all_nonprogram_flash_preserved',['verify',suffix,'-t','bin','-o',hex(0x10000000+end)])
    installed=folder/'installed-full-flash.bin'
    tool('complete_installed_snapshot_saved',['save','-v','-r','0x10000000','0x10400000','-t','bin',installed])
    require('installed_snapshot_exact',installed.stat().st_size==4194304 and installed.read_bytes()[:len(blob)]==blob and installed.read_bytes()[end:]==baseline.read_bytes()[end:])
    report.update(status='V043_FLASH_INSTALLED_VERIFIED_NOT_STARTED',remains_in_bootsel=True,log_regions_preserved=True,filesystem_preserved=True,installed_snapshot_sha256=sha(installed))
    record=dict(report,image=str(a.image.absolute()),installed_snapshot=str(installed),pico_serial=a.pico_serial)
    record_path=folder/'installation.json';record_path.write_text(json.dumps(record,indent=2),encoding='utf-8')
    (PRIVATE/'v043-install-selection.json').write_text(json.dumps(dict(record=str(record_path)),indent=2),encoding='utf-8')
except BaseException as exc:report['error']=str(exc)
finally:
    out=ROOT/'docs'/('V043_FLASH_INSTALL_'+stamp+'.json');out.write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
raise SystemExit(0 if report['status']=='V043_FLASH_INSTALLED_VERIFIED_NOT_STARTED' else 1)
