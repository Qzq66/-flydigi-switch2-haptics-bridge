import ctypes as C
import datetime
import importlib.util
import json
import pathlib
import time

path=pathlib.Path(__file__).with_name('flydigi-xinput.py')
spec=importlib.util.spec_from_file_location('xi',path)
xi=importlib.util.module_from_spec(spec)
spec.loader.exec_module(xi)
index=xi.flydigi_index()
report=dict(label='AFTER_RUNTIME_DISABLE_CLEANUP',persistent_commands=0,private_hid_commands=0,level=4096,max_level=65535,nominal_ms=180)
start=time.perf_counter()
try:
    xi.set_levels(index,4096,4096)
    report['start_status']='OK'
    time.sleep(0.18)
finally:
    xi.set_levels(index,0,0)
    report['stop_status']='OK'
    report['elapsed_ms']=round((time.perf_counter()-start)*1000,3)
    report['tested_at']=datetime.datetime.now().astimezone().isoformat()
    output=path.parent.parent/'outputs'/'flydigi-native-rumble-after.json'
    output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))
