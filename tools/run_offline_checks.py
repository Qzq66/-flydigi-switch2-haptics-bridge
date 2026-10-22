#!/usr/bin/env python3
"""Run only pure-data checks; never import Windows HID, XInput or output owners."""
import pathlib,subprocess,sys,json
root=pathlib.Path(__file__).absolute().parents[1]
work=root/'handoff/2026-10-22/work'
tests=['test-switch-hd-decode.py','test-bridge-runtime.py','test-bridge-prompt.py','test-bridge-input.py','test-pico-continuous-format.py','test-pico-capture-format.py']
results=[]
for name in tests:
    run=subprocess.run([sys.executable,str(work/name)],cwd=work.parent,capture_output=True,text=True,encoding='utf-8')
    result=dict(script=name,passed=run.returncode==0)
    if run.returncode:result['error']=run.stderr[-3000:]
    else:
        try:result['checks']=len(json.loads(run.stdout))
        except (ValueError,TypeError):pass
    results.append(result);print(json.dumps(result,ensure_ascii=False))
if '--write-report' in sys.argv:
    path=root/'docs/OFFLINE_EXPORT_VERIFICATION.json'
    path.write_text(json.dumps(dict(platform=sys.platform,python=sys.version,hardware_access=False,results=results),ensure_ascii=False,indent=2),encoding='utf-8')
raise SystemExit(0 if all(r['passed'] for r in results) else 1)
