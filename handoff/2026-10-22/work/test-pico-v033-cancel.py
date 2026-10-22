"""Verify USB-release cancellation before the scheduled registration pulse."""
import importlib.util, pathlib, time, json, datetime, struct
here=pathlib.Path(__file__).absolute().parent
spec=importlib.util.spec_from_file_location('candidate',here/'test-pico-capture-v033-ram.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
result={'checks':[],'status':'INCOMPLETE'}
def check(name,ok):
    result['checks'].append({'name':name,'passed':bool(ok)})
    if not ok:raise AssertionError(name)
try:
    m.lib.hid_init();matches=m.find_device();check('unique_v033',len(matches)==1)
    m.handle=m.lib.hid_open_path(matches[0]);check('open',bool(m.handle))
    check('RAM_candidate_magic',m.read_virtual(0x9000,8)==b'BCAP\x03\0\0\1')
    m.verified=True
    m.send(0x80,b'\4');m.sub(0x40,b'\2');m.sub(0x30,b'\0')
    check('armed_before_release',m.read_virtual(0x903c,1)==b'\1')
    m.send(0x80,b'\5')
    check('USB_release_cancelled',m.read_virtual(0x903c,1)==b'\11')
    m.send(0x80,b'\4');m.sub(0x30,b'\0')
    until=time.perf_counter()+4.2
    count=0
    while time.perf_counter()<until:
        p=m.receive(0x30)
        if p[3:6]!=b'\0'*3:raise AssertionError('Pulse after cancellation')
        count+=1
    check('no_press_after_resume_and_repeated_arm_command',count>200)
    raw=m.read_virtual(0x9030,16)
    check('zero_pressed_report_count',struct.unpack_from('<I',raw,4)[0]==0)
    check('cancel_flag_stays_latched',raw[12]==9)
    result.update(status='PASSED',reports_observed=count,diagnostics_hex=raw.hex())
except BaseException as e:result['error']=repr(e)
finally:
    if m.handle:
        if m.verified:
            try:m.send(0x80,b'\xfeRESETLAB')
            except BaseException as e:result['reset_error']=repr(e)
        m.lib.hid_close(m.handle)
    m.lib.hid_exit()
    output=here.parent/'outputs'/('pico-v033-cancel-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'.json')
    output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))
raise SystemExit(0 if result['status']=='PASSED' else 1)
