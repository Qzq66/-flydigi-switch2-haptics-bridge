import json
from types import SimpleNamespace
from bridge_input import convert,NEUTRAL
def state(**values):
    d=dict(buttons=0,lt=0,rt=0,lx=0,ly=0,rx=0,ry=0);d.update(values);return SimpleNamespace(**d)
checks=[]
def check(name,ok):checks.append(dict(name=name,passed=bool(ok)));assert ok,name
check('neutral_exact',convert(state())==NEUTRAL)
check('bottom_face_maps_to_switch_B',convert(state(buttons=0x1000))[0]==4)
check('right_face_maps_to_switch_A',convert(state(buttons=0x2000))[0]==8)
check('home_and_capture_never_synthesized',all(convert(state(buttons=1<<i))[1]&0x30==0 for i in range(16)))
check('center_drift_has_deadzone',convert(state(lx=100,ly=-100,rx=10,ry=20))==NEUTRAL)
def axes(p):return (p[0]|((p[1]&15)<<8),(p[1]>>4)|(p[2]<<4))
check('axes_match_synthetic_calibration_bounds',axes(convert(state(lx=-32768,ly=32767))[3:6])==(448,3648))
check('trigger_threshold',convert(state(lt=30,rt=30))==NEUTRAL and convert(state(lt=31,rt=31))[:3]==bytes([128,0,128]))
print(json.dumps(checks,indent=2))
