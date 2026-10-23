"""Consolidate separate lifecycle/capacity RAM evidence, without running devices."""
import hashlib,json,pathlib,subprocess,sys,argparse
ROOT=pathlib.Path(__file__).absolute().parents[1];sys.path.insert(0,str(ROOT/'handoff/2026-10-22/work'))
from pico_continuous_log import decode_sector,CAPACITY
p=argparse.ArgumentParser(description=__doc__)
for name in ('lifecycle','capacity','image','output'):p.add_argument('--'+name,type=pathlib.Path,required=True)
a=p.parse_args();manifest=json.loads(a.image.with_suffix('.manifest.json').read_text());image_sha=hashlib.sha256(a.image.read_bytes()).hexdigest()
checks=dict(image_hash=manifest['sha256']==image_sha);summaries={}
for case,path in (('lifecycle',a.lifecycle),('capacity',a.capacity)):
    r=json.loads(path.read_text(encoding='utf-8'));capture=r['capture'];wire=r['received_events']
    checks[case+'_strict_report']=r['status']=='PASSED_V043_RAM_'+case.upper() and all(r['checks'].values()) and r['timer_released'] is True
    checks[case+'_same_image']=r['ram_image_sha256']==image_sha
    checks[case+'_no_actuator_or_flash_output']=r['flydigi_access'] is False and r['physical_output'] is False and r['flash_write'] is False
    checks[case+'_full_flash_unchanged']=r['checks']['flash_before_matches'] and r['checks']['flash_after_matches']
    checks[case+'_journal_complete']=capture['crc_valid'] and capture['complete'] and capture['no_flash_marker']==1 and capture['stream_end']=='client_confirmed'
    checks[case+'_wire_contiguous']=[e['sequence'] for e in wire]==list(range(len(wire)))
    summaries[case]=dict(report=path.name,elapsed_seconds=r['elapsed_seconds'],records=capture['total_events'],motor_fields=len(wire),end_reason=capture['reason'],snapshot_bytes=r['snapshot_bytes_read'])
    if case=='lifecycle':checks['lifecycle_long_window']=117<=r['elapsed_seconds']<=123 and r['usb_input_milestones_seconds'][-1]>=115 and r['checks']['snapshot_rejects_normal_commands']
    else:checks['capacity_no_extras']=capture['total_events']==CAPACITY and capture['dropped_events']==0 and r['extra_write_completions_after_full']==16 and r['checks']['last_record_present_no_extra']
checks['v042_source_unchanged']=subprocess.run(['git','diff','--quiet','main','--','handoff/2026-10-22/outputs/pico-haptics-bridge-v042'],cwd=ROOT).returncode==0
sources=ROOT/'handoff/2026-10-22/outputs/pico-haptics-bridge-v043'
result=dict(status='PASSED_V043_RAM_DIAGNOSTICS' if all(checks.values()) else 'INCOMPLETE',checks=checks,cases=summaries,ram_image_sha256=image_sha,
    source_sha256={v.relative_to(ROOT).as_posix():hashlib.sha256(v.read_bytes()).hexdigest() for v in sources.iterdir() if v.is_file()},
    scope='PC-side neutral input, duration, full-journal boundary and read-only RAM snapshot; not Switch 2 or game validation',
    pico_flash_installed='retained v042, persistent generation 10 unchanged',flash_candidate_installed=False,github_uploaded=False)
with a.output.open('x',encoding='utf-8') as h:json.dump(result,h,indent=2)
print(json.dumps({k:v for k,v in result.items() if k!='source_sha256'},indent=2));raise SystemExit(0 if all(checks.values()) else 1)
