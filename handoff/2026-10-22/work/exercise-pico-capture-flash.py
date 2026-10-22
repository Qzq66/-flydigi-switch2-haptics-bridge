"""Brief PC-only input to the exact Flash capture build; never sends reset."""
import datetime
import importlib.util
import json
import pathlib
import sys

HERE=pathlib.Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('candidate',HERE/'test-pico-capture-ram.py')
lab=importlib.util.module_from_spec(sp);sp.loader.exec_module(lab)
report=dict(started_at=datetime.datetime.now().astimezone().isoformat(),checks=[],switch2_tested=False,physical_output=False)
lab.report=report
lab.lib.hid_init()
try:
    matches=lab.find_device();lab.check('single_capture_build',len(matches)==1)
    lab.handle=lab.lib.hid_open_path(matches[0])
    if not lab.handle:raise OSError('Capture interface open failed')
    marker=lab.read_virtual(0x9000,8)
    lab.check('Flash_build_marker',marker[:5]==b'BCAP\x03' and marker[7]==0)
    lab.verified=True
    for cmd in (1,2,3,2):
        lab.send(0x80,bytes([cmd]));lab.receive(0x81,lambda p:p[1]==cmd)
    lab.send(0x80,b'\x04')
    lab.check('device_info',lab.sub(2)[13]==0x82)
    lab.check('synthetic_calibration',lab.read_virtual(0x6040,3)==bytes.fromhex('000880'))
    lab.check('input_mode',lab.sub(3,b'\x30')[13]==0x80)
    for _ in range(3):lab.receive(0x30)
    pattern=bytes.fromhex('1112233445566778')
    lab.send(0x10,b'\0'+pattern)
    lab.check('captured_pattern',lab.read_virtual(0x9020,8)==pattern)
    report['expected_capture_rumble']=pattern.hex()
    report['status']='PC_EXERCISE_PASSED_WAITING_FOR_AUTOMATIC_SAVE'
except BaseException as exc:
    report['status']='INCOMPLETE';report['error']=f'{type(exc).__name__}: {exc}'
finally:
    if lab.handle:lab.lib.hid_close(lab.handle)
    lab.lib.hid_exit()
    output=lab.ro.ROOT/'outputs'/'pico-capture-flash-exercise.json'
    output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))
sys.exit(0 if report['status']=='PC_EXERCISE_PASSED_WAITING_FOR_AUTOMATIC_SAVE' else 1)
