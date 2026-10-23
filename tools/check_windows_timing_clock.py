"""Check a shared cross-process clock without devices or network."""
import datetime,hashlib,json,pathlib,platform,subprocess,sys,time
ROOT=pathlib.Path(__file__).absolute().parents[1]
time.perf_counter();time.sleep(.1)
before=dict(perf=time.perf_counter(),monotonic=time.monotonic())
child=json.loads(subprocess.check_output([sys.executable,'-c','import time,json; print(json.dumps(dict(perf=time.perf_counter(),monotonic=time.monotonic())))'],text=True))
after=dict(perf=time.perf_counter(),monotonic=time.monotonic())
shared={k:before[k]<=child[k]<=after[k] for k in before}
result=dict(status='PASSED_SHARED_MONOTONIC_CLOCK' if shared['monotonic'] else 'INCOMPLETE',python=platform.python_version(),hardware_access=False,
    before=before,child=child,after=after,shared=shared,
    previous_timing_source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ('tools/input_timing.py','tools/input_timing_window.py','handoff/2026-10-22/work/bridge-switch-live.py')})
output=ROOT/'docs'/('V043_TIMING_CLOCK_'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'.json')
with output.open('x',encoding='utf-8') as h:json.dump(result,h,indent=2)
print(json.dumps(result,indent=2));raise SystemExit(0 if shared['monotonic'] else 1)
