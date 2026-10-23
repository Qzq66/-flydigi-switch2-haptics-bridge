"""Freeze v043 evidence and private recovery files; no device or network access."""
import datetime,hashlib,json,pathlib,shutil,subprocess,zipfile
from v043_game_gate import authorize,ROOT
from assess_v043_staged_game import assess
from pico_continuous_log import decode_slots
WORK=ROOT/'handoff/2026-10-22/work';PRIVATE=WORK/'private'
OUTPUT=ROOT/'docs/V043_BASELINE_2026-10-24.json'
if OUTPUT.exists():raise ValueError('Baseline already exists; preserve it and use a new version')
def load(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
record_path=pathlib.Path(load(PRIVATE/'v043-install-selection.json')['record']);record=load(record_path)
snapshot=pathlib.Path(record['installed_snapshot']);image=pathlib.Path(record['image'])
expected='3f7df3484644560548917013a66caac2c7f4b6a4307768fbf377e3fb4e751f50'
if record['status']!='V043_FLASH_READY_VERIFIED' or record['baseline_generation']!=15 or sha(image)!=expected or record['firmware_sha256']!=expected:raise ValueError('Reviewed candidate identity mismatch')
if snapshot.stat().st_size!=4194304 or sha(snapshot)!=record['installed_snapshot_sha256']:raise ValueError('Complete snapshot changed')
data=snapshot.read_bytes()
if data[:image.stat().st_size]!=image.read_bytes():raise ValueError('Snapshot program differs from accepted image')
capture=decode_slots(data[0xe0000:0x100000]);latest=capture['newest']
if latest['generation']!=15 or not latest['complete'] or latest['stream_end']!='client_confirmed':raise ValueError('Current journal is not the successful complete generation 15')
bundle=ROOT/'docs/V043_STAGED_GAME_PREREQUISITE_20261023.json';trials=[]
for stamp,cap_name,base_name in (
    ('20261023-234407','V043_HOST_CAPTURE_20261023-235027.json','V043_HOST_CAPTURE_20261023-224226.json'),
    ('20261023-235855','V043_HOST_CAPTURE_20261024-000336.json','V043_HOST_CAPTURE_20261023-235027.json')):
    program_name='WINDOWS_V043_GAME_RECHECK_'+stamp+'.json';assessment_name='V043_STAGED_GAME_ASSESSMENT_'+stamp+'.json'
    program=load(ROOT/'docs'/program_name);cap=load(ROOT/'docs'/cap_name)['newest'];base=load(ROOT/'docs'/base_name)['newest'];saved=load(ROOT/'docs'/assessment_name)
    flags=[saved['checks'][key] is True for key in ('human_game_pulse','human_prearm_silent','human_stopped')]
    proof=authorize(bundle,program['firmware_preflight']);result=assess(program,cap,base,proof,*flags)
    if result!=saved or result['status']!='PASSED_V043_120S_STAGED_GAME_LIMITED_NOTIFICATION' or not all(result['checks'].values()):raise ValueError('Recomputed trial evidence differs: '+stamp)
    trials.append(dict(stamp=stamp,generation=result['journal_generation'],baseline_generation=base['generation'],motor_fields=result['motor_fields'],live_seconds=result['observed_live_seconds'],firmware_sha256=program['firmware_preflight']['firmware_sha256'],program=program_name,capture=cap_name,assessment=assessment_name))
if [r['generation'] for r in trials]!=[14,15] or [r['baseline_generation'] for r in trials]!=[13,14] or any(r['firmware_sha256']!=expected for r in trials):raise ValueError('Independent trial chain mismatch')
if latest!=load(ROOT/'docs'/trials[1]['capture'])['newest']:raise ValueError('Raw snapshot journal differs from published successful capture')
physical=load(ROOT/'docs/V043_READY_BASELINE_20261024-000440.json')
if physical['full_flash_sha256']!=sha(snapshot) or not physical['physical_full_readback_verified']:raise ValueError('Prior physical verification attestation mismatch')
old_pointer=load(PRIVATE/'staged-game-baseline-selection.json');old_root=pathlib.Path(old_pointer['root'])/'LOCAL_PRIVATE_RECOVERY'
old_manifest=load(ROOT/'docs/STAGED_GAME_BASELINE_2026-10-23.json')
old_v042=old_root/'current-v042-full.bin';original=old_root/'original-micropython-full.bin';old_v040=old_root/'previous-v040-full.bin'
old_v040_record=load(PRIVATE/'v042-pre-flash-selection.json')
for path,digest in ((old_v042,old_manifest['current_full_flash_sha256']),(original,'09762691d3fddf3ba592db0bb6f520cb2384423f37194e7974089c9b0f700593'),(old_v040,old_v040_record['sha256'].lower())):
    if path.stat().st_size!=4194304 or sha(path)!=digest:raise ValueError('Recovery material mismatch: '+path.name)
working=pathlib.Path(load(PRIVATE/'rollback-selection.json')['root'])/'work/private'
for name in ('bridge_credentials.h','bridge-session.json'):
    if (working/name).read_bytes()!=(old_root/name).read_bytes():raise ValueError('Credential/session changed from the validated local network')
stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S');folder=PRIVATE/'baselines'/('v043-game-'+stamp);folder.mkdir(parents=True,exist_ok=False)
listed=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=ROOT).decode('utf-8').split('\0')
suffixes={'.py','.ps1','.md','.json','.c','.h','.cmake','.sh','.yml','.yaml','.toml'}
files=[]
for name in sorted(set(filter(None,listed))):
    relative=pathlib.PurePosixPath(name);path=ROOT/relative
    if 'private' in relative.parts or '..' in relative.parts or path==OUTPUT or not path.is_file():continue
    if path.suffix not in suffixes and path.name not in ('CMakeLists.txt','.gitignore','.gitattributes','LICENSE','LICENSE.txt') and not path.name.endswith('-LICENSE'):continue
    if path.is_symlink():raise ValueError('Refusing symlink in frozen source set')
    target=folder/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
    if sha(target)!=sha(path):raise ValueError('Source copy mismatch')
    files.append(dict(path=relative.as_posix(),bytes=path.stat().st_size,sha256=sha(path)))
assets={'current-v043-full.bin':snapshot,'current-v043-program.bin':image,'v042-full.bin':old_v042,'original-micropython-full.bin':original,'v040-full.bin':old_v040,
    'bridge_credentials.h':working/'bridge_credentials.h','bridge-session.json':working/'bridge-session.json','v043-installation-record.json':record_path,
    'flydigi-pre-trial14.json':PRIVATE/'v042-input-backup-20261023-234407.json','flydigi-pre-trial15.json':PRIVATE/'v042-input-backup-20261023-235855.json'}
recovery=folder/'LOCAL_PRIVATE_RECOVERY';recovery.mkdir();private_assets=[]
for name,path in assets.items():
    shutil.copy2(path,recovery/name)
    if sha(recovery/name)!=sha(path):raise ValueError('Private recovery copy mismatch')
    private_assets.append(dict(path='LOCAL_PRIVATE_RECOVERY/'+name,bytes=path.stat().st_size,sha256=sha(path)))
manifest=dict(status='FROZEN_LOCAL_V043_TWO_GAME_TRIAL_BASELINE',created_at=datetime.datetime.now().astimezone().isoformat(),
    firmware_sha256=expected,current_full_flash_sha256=sha(snapshot),current_full_flash_bytes=4194304,journal_generation=15,trials=trials,
    prior_physical_verification_report='V043_READY_BASELINE_20261024-000440.json',device_access_this_run=False,flash_write=False,hardware_output_started=False,
    recovery_verified=True,files=files,private_assets=private_assets,archive_private=True,github_uploaded=False,
    scope='Two independent offline 120s same-door notification trials; not original HD fidelity, all-game compatibility, or long-term stability')
(folder/'BASELINE_MANIFEST.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
archive=folder.with_suffix('.zip')
with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as z:
    for path in sorted(folder.rglob('*')):
        if path.is_file():z.write(path,path.relative_to(folder).as_posix())
with zipfile.ZipFile(archive) as z:
    if z.testzip() is not None:raise ValueError('Archive CRC failed')
    for item in files+private_assets:
        if hashlib.sha256(z.read(item['path'])).hexdigest()!=item['sha256']:raise ValueError('Archived file hash mismatch')
manifest.update(archive_sha256=sha(archive),archive_bytes=archive.stat().st_size,archive_crc_verified=True,archived_files_verified=True)
# The public manifest exposes no private paths, board identity, or credential hashes.
public=dict(manifest);public.pop('private_assets')
with OUTPUT.open('x',encoding='utf-8') as h:json.dump(public,h,indent=2)
(PRIVATE/'v043-game-baseline-selection.json').write_text(json.dumps(dict(root=str(folder),archive=str(archive),archive_sha256=manifest['archive_sha256'],manifest=str(OUTPUT)),indent=2),encoding='utf-8')
print(json.dumps(dict(status=manifest['status'],source_evidence_files=len(files),private_asset_count=len(private_assets),archive_bytes=manifest['archive_bytes'],archive_crc_verified=True,archived_files_verified=True,device_access=False,public_manifest=str(OUTPUT)),indent=2))
