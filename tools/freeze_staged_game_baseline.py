"""Freeze current local sources/evidence and a verified private Flash snapshot.

No device/network access. The archive contains recovery binaries and is private.
"""
import hashlib,json,pathlib,shutil,zipfile,datetime
ROOT=pathlib.Path(__file__).absolute().parents[1];WORK=ROOT/'handoff/2026-10-22/work'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
snapshot=WORK/'private/v042-full-baseline-20261023.bin'
image=ROOT/'build/pico-v042-live-flash/pico_pro_capture.bin'
expected='1b4746c62f7e80ddb47d49b08cd3bbc3a6be0f4c1b43a3d44fe2c8e413d6cdc3'
if sha(image)!=expected or snapshot.stat().st_size!=4194304:raise ValueError('Baseline image or complete snapshot mismatch')
data=snapshot.read_bytes()
if data[:image.stat().st_size]!=image.read_bytes():raise ValueError('Snapshot program mismatch')
latest=WORK/'private/v042-capture-20261023-162326.bin'
if data[0xe0000:0x100000]!=latest.read_bytes():raise ValueError('Snapshot differs from latest verified journal')
reports=[]
for stamp in ('20261023-161628','20261023-162326'):
    path=ROOT/'docs'/('WINDOWS_V042_STAGED_GAME_ASSESSMENT_'+stamp+'.json')
    result=json.loads(path.read_text(encoding='utf-8'))
    if result['status']!='PASSED_STAGED_GAME_LIMITED_NOTIFICATION' or not all(result['checks'].values()):raise ValueError('Success evidence incomplete')
    reports.append(path)
original=pathlib.Path(r'C:\Users\quziqi\Documents\ChatGPT\86pro手柄震动\work\backups\pico-pre-capture-20261022-124037.bin')
if sha(original)!='09762691d3fddf3ba592db0bb6f520cb2384423f37194e7974089c9b0f700593':raise ValueError('Original MicroPython recovery mismatch')
pointer=json.loads((WORK/'private/v042-pre-flash-selection.json').read_text(encoding='utf-8-sig'));old=pathlib.Path(pointer['path'])
if sha(old).lower()!=pointer['sha256'].lower():raise ValueError('Old full recovery mismatch')
stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S');folder=WORK/'private/baselines'/('staged-game-'+stamp);folder.mkdir(parents=True,exist_ok=False)
paths=set(WORK.glob('*.py'))|set(ROOT.glob('tools/*.py'))|set(ROOT.glob('tools/*.ps1'))
firmware=ROOT/'handoff/2026-10-22/outputs/pico-haptics-bridge-v042'
paths.update(p for p in firmware.iterdir() if p.is_file() and (p.suffix in ('.c','.h') or p.name=='CMakeLists.txt'))
paths.update(ROOT.glob('docs/WINDOWS_*.json'));paths.update(ROOT.glob('docs/WINDOWS_*.md'))
paths.update((ROOT/'docs/STATUS.md',ROOT/'.gitignore'))
files=[]
for path in sorted(paths):
    relative=path.relative_to(ROOT);target=folder/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
    files.append(dict(path=relative.as_posix(),bytes=path.stat().st_size,sha256=sha(path)))
recovery=folder/'LOCAL_PRIVATE_RECOVERY';recovery.mkdir()
for name,path in (('current-v042-full.bin',snapshot),('original-micropython-full.bin',original),('previous-v040-full.bin',old)):
    shutil.copy2(path,recovery/name)
selection=json.loads((WORK/'private/rollback-selection.json').read_text(encoding='utf-8'))
secrets=pathlib.Path(selection['root'])/'work/private'
for name in ('bridge_credentials.h','bridge-session.json'):
    shutil.copy2(secrets/name,recovery/name)
manifest=dict(status='FROZEN_LOCAL_STAGED_GAME_BASELINE',created_at=datetime.datetime.now().astimezone().isoformat(),
    scope='Two independent offline door-entry trials; calibrated 120ms +/-12 notifications, not original HD rumble fidelity',
    validated_generations=[9,10],exact_motor_fields=[581,563],firmware_sha256=expected,
    current_full_flash_sha256=sha(snapshot),current_full_flash_bytes=snapshot.stat().st_size,
    original_recovery_verified=True,previous_recovery_verified=True,files=files,
    success_reports=[p.name for p in reports],archive_private=True,hardware_output_started=False,github_uploaded=False)
(folder/'BASELINE_MANIFEST.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf-8')
archive=folder.with_suffix('.zip')
with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as z:
    for path in sorted(folder.rglob('*')):
        if path.is_file():z.write(path,path.relative_to(folder).as_posix())
with zipfile.ZipFile(archive) as z:
    if z.testzip() is not None:raise ValueError('Archive CRC failed')
    for item in files:
        if hashlib.sha256(z.read(item['path'])).hexdigest()!=item['sha256']:raise ValueError('Archived source mismatch')
    if hashlib.sha256(z.read('LOCAL_PRIVATE_RECOVERY/current-v042-full.bin')).hexdigest()!=sha(snapshot):raise ValueError('Archived Flash mismatch')
private_pointer=WORK/'private/staged-game-baseline-selection.json'
private_pointer.write_text(json.dumps(dict(root=str(folder),archive=str(archive),archive_sha256=sha(archive)),indent=2),encoding='utf-8')
manifest.update(archive_sha256=sha(archive),archive_crc_verified=True,archived_sources_verified=True)
output=ROOT/'docs/STAGED_GAME_BASELINE_2026-10-23.json'
with output.open('x',encoding='utf-8') as h:json.dump(manifest,h,indent=2,ensure_ascii=False)
print(json.dumps(dict(status=manifest['status'],source_evidence_files=len(files),archive_bytes=archive.stat().st_size,archive_crc_verified=True,archived_sources_verified=True,private_archive=True,output=str(output)),indent=2))
