"""Refresh a readback-verified journal baseline, preserving the original install record."""
import argparse,datetime,json,pathlib,subprocess,sys
from v043_installation import ROOT,PRIVATE,sha
sys.path.insert(0,str(ROOT/'handoff/2026-10-22/work'))
from pico_continuous_log import decode_slots
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--snapshot',type=pathlib.Path,required=True);p.add_argument('--picotool',type=pathlib.Path,required=True);a=p.parse_args()
stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S');pointer=PRIVATE/'v043-install-selection.json'
selection=json.loads(pointer.read_text(encoding='utf-8'));oldpath=pathlib.Path(selection['record']);old=json.loads(oldpath.read_text(encoding='utf-8'))
prior=pathlib.Path(old['installed_snapshot']);image=pathlib.Path(old['image']);blob=a.snapshot.read_bytes();before=prior.read_bytes()
if sha(prior)!=old['installed_snapshot_sha256'] or sha(image)!=old['firmware_sha256']:raise ValueError('Original evidence changed')
if len(blob)!=4194304 or blob[:0xe0000]!=before[:0xe0000] or blob[0x100000:]!=before[0x100000:]:raise ValueError('Changes outside journal; refused')
capture=decode_slots(blob[0xe0000:0x100000])['newest'];delta=(capture['generation']-old['baseline_generation'])&0xffffffff
if not (0<delta<0x80000000) or not capture['complete'] or capture['no_flash_marker']!=0:raise ValueError('Fresh complete persistent generation required')
with (PRIVATE/('v043-refresh-'+stamp+'.txt')).open('w',encoding='utf-8') as console:
    r=subprocess.run([str(a.picotool),'verify',str(a.snapshot),'-t','bin','-o','0x10000000','--ser',old['pico_serial']],stdout=console,stderr=subprocess.STDOUT,timeout=40)
if r.returncode:raise ValueError('Actual board differs from readback snapshot; refused')
new=dict(old,status='V043_FLASH_READY_VERIFIED',previous_record=str(oldpath),installed_snapshot=str(a.snapshot.absolute()),installed_snapshot_sha256=sha(a.snapshot),baseline_generation=capture['generation'],refreshed_at=datetime.datetime.now().astimezone().isoformat())
record=PRIVATE/('v043-ready-'+stamp+'.json');record.write_text(json.dumps(new,indent=2),encoding='utf-8')
pointer.write_text(json.dumps(dict(record=str(record)),indent=2),encoding='utf-8')
public=dict(status=new['status'],firmware_sha256=new['firmware_sha256'],full_flash_sha256=new['installed_snapshot_sha256'],baseline_generation=capture['generation'],previous_generation=old['baseline_generation'],outside_journal_unchanged=True,physical_full_readback_verified=True,flash_write=False,flydigi_access=False,remains_in_bootsel=True)
out=ROOT/'docs'/('V043_READY_BASELINE_'+stamp+'.json');out.write_text(json.dumps(public,indent=2),encoding='utf-8');print(json.dumps(public,indent=2))
