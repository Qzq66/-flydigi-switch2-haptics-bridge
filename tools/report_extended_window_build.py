"""Verify existing compile-only candidate products and export a safe build report."""
import hashlib,json,pathlib,subprocess,datetime
ROOT=pathlib.Path(__file__).absolute().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
products={}
for profile,extension in (('ram','uf2'),('flash','bin')):
    folder=ROOT/'build'/('pico-v043-120s-'+profile+'-compile-only');image=folder/('pico_pro_capture.'+extension)
    manifest=json.loads((folder/'pico_pro_capture.manifest.json').read_text())
    if sha(image)!=manifest['sha256'] or image.stat().st_size!=manifest['bytes']:raise ValueError('Candidate product mismatch')
    products[profile]={k:v for k,v in manifest.items() if k!='file'}
    products[profile]['path']=image.relative_to(ROOT).as_posix()
    if profile=='ram' and (int(manifest['minimum_address'],16)<0x20000000 or int(manifest['maximum_end'],16)>0x20082000):raise ValueError('RAM bounds')
    if profile=='flash' and (not manifest['program_excludes_logs_and_filesystem'] or int(manifest['program_erase_end'],16)>0xe0000):raise ValueError('Flash bounds')
nm=pathlib.Path(r'C:\Users\quziqi\Documents\Codex\pico-work-20261022\pico-tools\bin\arm-none-eabi-nm.exe')
symbols=subprocess.check_output([str(nm),str(ROOT/'build/pico-v043-120s-ram-compile-only/pico_pro_capture.elf')],text=True)
if any(line.split()[-1] in ('flash_range_program','flash_range_erase') for line in symbols.splitlines() if line.split()):raise ValueError('RAM contains Flash mutation routines')
subprocess.run(['git','diff','--exit-code','main','--','handoff/2026-10-22/outputs/pico-haptics-bridge-v042'],cwd=ROOT,check=True,stdout=subprocess.PIPE)
baseline=json.loads((ROOT/'docs/STAGED_GAME_BASELINE_2026-10-23.json').read_text(encoding='utf-8'))
current=ROOT/'build/pico-v042-live-flash/pico_pro_capture.bin'
if sha(current)!=baseline['firmware_sha256']:raise ValueError('Retained v042 image changed')
offline=json.loads((ROOT/'docs/V043_120S_OFFLINE_20261023.json').read_text(encoding='utf-8'))
if not all(r['passed'] for r in offline['results']):raise ValueError('Offline regression failure')
candidate=ROOT/'handoff/2026-10-22/outputs/pico-haptics-bridge-v043'
sources={p.relative_to(ROOT).as_posix():sha(p) for p in candidate.iterdir() if p.is_file()}
result=dict(status='COMPILE_ONLY_V043_120S_VERIFIED_NOT_INSTALLED',created_at=datetime.datetime.now().astimezone().isoformat(),
    credentials='public placeholders; unsuitable for actual hotspot testing',hardware_access=False,flash_written=False,rumble_output=False,
    live_seconds=120,boot_limit_seconds=180,host_live_seconds=122,discovery_seconds=120,guardian_seconds=270,
    journal_capacity=2725,journal_full_action='seal new USB callbacks after final accepted report; disconnect and drain; reason=capacity_limit',
    amplitude_and_count_limits_changed=False,heartbeat_threshold_changed=False,baseline_v042_source_and_image_unchanged=True,
    ram_flash_mutation_symbols_absent=True,offline_checks=offline['total_checks'],products=products,source_sha256=sources,
    hardware_validation='not performed; capacity-boundary callback and extended timing remain unverified on device')
output=ROOT/'docs/V043_120S_BUILD_20261023.json'
with output.open('x',encoding='utf-8') as h:json.dump(result,h,indent=2)
print(json.dumps({k:v for k,v in result.items() if k not in ('products','source_sha256')},indent=2))
