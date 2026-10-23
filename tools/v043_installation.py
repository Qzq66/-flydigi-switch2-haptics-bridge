"""Private, board-bound installation evidence; no device access on import."""
import hashlib,json,pathlib,subprocess
ROOT=pathlib.Path(__file__).absolute().parents[1]
PRIVATE=ROOT/'handoff/2026-10-22/work/private'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def verify_installed(record_path,picotool,serial):
    record=json.loads(pathlib.Path(record_path).read_text(encoding='utf-8'))
    if record.get('status') not in ('V043_FLASH_INSTALLED_VERIFIED_NOT_STARTED','V043_FLASH_READY_VERIFIED') or record.get('pico_serial')!=serial:
        raise ValueError('A successful v043 installation record for this board is required')
    image=pathlib.Path(record['image']);full=pathlib.Path(record['installed_snapshot'])
    if sha(image)!=record['firmware_sha256'] or full.stat().st_size!=4194304 or sha(full)!=record['installed_snapshot_sha256']:
        raise ValueError('Installed image or complete snapshot changed')
    with (PRIVATE/'v043-preflight-console.txt').open('a',encoding='utf-8') as console:
        result=subprocess.run([str(picotool),'verify',str(full),'-t','bin','-o','0x10000000','--ser',serial],stdout=console,stderr=subprocess.STDOUT,timeout=30)
    if result.returncode:raise ValueError('Physical Flash does not match the v043 installation; keep BOOTSEL')
    return dict(verified=True,variant='v043',firmware_sha256=record['firmware_sha256'],
        installed_snapshot_sha256=record['installed_snapshot_sha256'],baseline_generation=record['baseline_generation'])
