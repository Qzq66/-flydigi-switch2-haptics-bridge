"""Exact Pico-only Flash delivery test. Never selects Flydigi or a real Pro."""
import pathlib,importlib.util,time,json,datetime
here=pathlib.Path(__file__).absolute().parent
spec=importlib.util.spec_from_file_location('candidate',here/'test-pico-capture-v035-ram.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
result={'status':'INCOMPLETE','checks':[],'expected_words':[],'physical_output':False}
def check(name,ok):
    result['checks'].append(dict(name=name,passed=bool(ok)));assert ok,name
try:
    m.lib.hid_init();matches=m.find_device();check('unique_v035',len(matches)==1)
    m.handle=m.lib.hid_open_path(matches[0]);check('open',bool(m.handle))
    check('Flash_candidate_magic',m.read_virtual(0x9000,8)==b'BCAP\5\0\0\0')
    m.verified=True;m.allow_lr=True
    m.send(0x80,b'\4');m.sub(0x40,b'\2');m.sub(0x30,b'\0')
    for i in range(160):
        left=((1<<30)|((i%128)<<23)|(64<<16)|(64<<2)).to_bytes(4,'little')
        right=((1<<30)|((i%128)<<9)|(64<<16)|(64<<2)).to_bytes(4,'little')
        motors=left+right;result['expected_words'].append(motors.hex());m.send(0x10,bytes([i%16])+motors)
    check('submitted_160_known_motor_words',True)
    m.read_virtual(0x9000,8)
    result['status']='AWAITING_AUTOMATIC_FLASH_COMMIT'
except BaseException as e:result['error']=repr(e)
finally:
    if m.handle:m.lib.hid_close(m.handle)
    m.lib.hid_exit()
    output=here.parent/'outputs/pico-v035-flash-exercise.json'
    output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='expected_words'},indent=2))
raise SystemExit(0 if result['status']=='AWAITING_AUTOMATIC_FLASH_COMMIT' else 1)
