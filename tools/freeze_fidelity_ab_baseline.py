"""Freeze the two successful PC A/B trials and prior recovery assets; no hardware."""
import datetime,hashlib,json,pathlib,shutil,subprocess,zipfile
from fidelity_ab_plan import ROOT,build_plan,validate_plan,ab_child_succeeded
PRIVATE=ROOT/'handoff/2026-10-22/work/private';OUTPUT=ROOT/'docs/FIDELITY_AB_BASELINE_2026-10-24.json'
load=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
if OUTPUT.exists():raise ValueError('Preserve existing baseline; use a new version')
plan_path=ROOT/'docs/FIDELITY_AB_PLAN_2026-10-24_V2.json';plan=load(plan_path);validate_plan(plan)
offline=load(ROOT/'docs/FIDELITY_AB_ENTRY_OFFLINE_2026-10-24_V2.json')
if offline['status']!='PASSED_OFFLINE_FIDELITY_AB_ENTRY' or offline['tests']!=20 or offline['failures'] or offline['errors']:raise ValueError('Offline A/B proof invalid')
for name,digest in offline['source_sha256'].items():
    if sha(ROOT/name)!=digest:raise ValueError('Reviewed source changed: '+name)
trials=[]
for stamp in ('20261024-144048','20261024-144511'):
    program_path=ROOT/'docs'/('FIDELITY_AB_RUN_'+stamp+'.json');assessment_path=ROOT/'docs'/('FIDELITY_AB_ASSESSMENT_'+stamp+'.json')
    program=load(program_path);saved=load(assessment_path);c=program['child']
    if not ab_child_succeeded(c,program['child_exit'],plan,program['guardian_killed_child']):raise ValueError('Child no longer passes')
    if saved['program_sha256']!=sha(program_path) or saved['plan_sha256']!=sha(plan_path) or not all(saved['checks'].values()) or len(saved['checks'])!=15:raise ValueError('Assessment differs')
    if program['status']!='PASSED_FIDELITY_AB_PROGRAM_AND_CONFIG' or not program['runtime_disable_ack'] or not program['configuration_unchanged']:raise ValueError('Parent no longer passes')
    trials.append(dict(stamp=stamp,program=program_path.name,assessment=assessment_path.name,checks=15,confirmed_gap_seconds=saved['confirmed_gap_seconds']))
prior=load(PRIVATE/'v043-repeated-baseline-selection.json');prior_root=pathlib.Path(prior['root']);prior_archive=pathlib.Path(prior['archive'])
if sha(prior_archive)!=prior['archive_sha256']:raise ValueError('Prior frozen archive changed')
internal=load(prior_root/'BASELINE_MANIFEST.json')
with zipfile.ZipFile(prior_archive) as z:
    if z.testzip() is not None:raise ValueError('Prior archive CRC failed')
    for item in internal['files']+internal['private_assets']:
        if hashlib.sha256(z.read(item['path'])).hexdigest()!=item['sha256']:raise ValueError('Prior archived asset changed')
stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S');folder=PRIVATE/'baselines'/('fidelity-ab-'+stamp);folder.mkdir(parents=True,exist_ok=False)
listed=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=ROOT).decode('utf-8').split('\0')
suffixes={'.py','.ps1','.md','.json','.c','.h','.cmake','.sh','.yml','.yaml','.toml'};files=[]
for name in sorted(set(filter(None,listed))):
    relative=pathlib.PurePosixPath(name);path=ROOT/relative
    if 'private' in relative.parts or '..' in relative.parts or path==OUTPUT or not path.is_file():continue
    csv_preview=path.suffix=='.csv' and relative.parts[0]=='docs' and any(part.startswith('fidelity-candidate-') for part in relative.parts)
    if path.suffix not in suffixes and not csv_preview and path.name not in ('CMakeLists.txt','.gitignore','.gitattributes','LICENSE','LICENSE.txt') and not path.name.endswith('-LICENSE'):continue
    if path.is_symlink():raise ValueError('Refusing symlink')
    target=folder/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
    if sha(path)!=sha(target):raise ValueError('Source copy mismatch')
    files.append(dict(path=relative.as_posix(),bytes=path.stat().st_size,sha256=sha(path)))
recovery=folder/'LOCAL_PRIVATE_RECOVERY';recovery.mkdir();private_assets=[]
assets={pathlib.Path(item['path']).name:prior_root/item['path'] for item in internal['private_assets']}
for trial in trials:assets['flydigi-pre-ab-'+trial['stamp']+'.json']=PRIVATE/('fidelity-ab-backup-'+trial['stamp']+'.json')
for name,path in assets.items():
    shutil.copy2(path,recovery/name)
    if sha(path)!=sha(recovery/name):raise ValueError('Recovery copy mismatch')
    private_assets.append(dict(path='LOCAL_PRIVATE_RECOVERY/'+name,bytes=path.stat().st_size,sha256=sha(path)))
manifest=dict(status='FROZEN_LOCAL_TWO_FIDELITY_AB_BASELINE',created_at=datetime.datetime.now().astimezone().isoformat(),trials=trials,
    plan_sha256=sha(plan_path),last_verified_pico_generation=20,current_full_flash_sha256=internal['current_full_flash_sha256'],
    firmware_sha256=internal['firmware_sha256'],device_access_this_run=False,flash_write=False,hardware_output_started=False,
    archive_private=True,github_uploaded=False,files=files,private_assets=private_assets,
    scope='Two PC-only perceptual A/B trials; not original actuator fidelity, Switch live dual-band acceptance or physical calibration')
(folder/'BASELINE_MANIFEST.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8');archive=folder.with_suffix('.zip')
with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as z:
    for path in sorted(folder.rglob('*')):
        if path.is_file():z.write(path,path.relative_to(folder).as_posix())
with zipfile.ZipFile(archive) as z:
    if z.testzip() is not None:raise ValueError('New archive CRC failed')
    for item in files+private_assets:
        if hashlib.sha256(z.read(item['path'])).hexdigest()!=item['sha256']:raise ValueError('Archived file mismatch')
public={k:v for k,v in manifest.items() if k!='private_assets'}
public.update(archive_sha256=sha(archive),archive_bytes=archive.stat().st_size,archive_crc_verified=True,archived_files_verified=True)
with OUTPUT.open('x',encoding='utf-8') as out:json.dump(public,out,indent=2)
(PRIVATE/'fidelity-ab-baseline-selection.json').write_text(json.dumps(dict(root=str(folder),archive=str(archive),archive_sha256=sha(archive),manifest=str(OUTPUT)),indent=2),encoding='utf-8')
print(json.dumps(dict(status=public['status'],source_evidence_files=len(files),private_asset_count=len(private_assets),archive_bytes=public['archive_bytes'],archive_crc_verified=True,archived_files_verified=True,device_access=False),indent=2))
