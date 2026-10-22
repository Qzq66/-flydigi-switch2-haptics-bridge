"""Read-only human button challenge; no HID output, XInputSetState or config writes."""
import time,json,pathlib,datetime
import xinput_readonly as xi
report=dict(status='INCOMPLETE',readonly=True,expected_button='physical bottom A',press_seen=False,release_seen=False)
try:
    slots=xi.connected()
    if len(slots)!=1:raise ValueError('Exactly one XInput source required')
    slot=slots[0];report['slot']=slot;until=time.perf_counter()+50
    while time.perf_counter()<until:
        state=xi.read(slot)
        if state is None:raise OSError('Source disconnected')
        buttons=state.gamepad.buttons
        if buttons&0x1000:report['press_seen']=True
        elif report['press_seen'] and not buttons:report['release_seen']=True;report['status']='HUMAN_SOURCE_CHALLENGE_PASSED';break
        time.sleep(.01)
except BaseException as e:report['error']=repr(e)
path=pathlib.Path(__file__).absolute().parent.parent/'outputs'/('xinput-source-confirmation-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'.json')
path.write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2));print(str(path))
raise SystemExit(0 if report['status']=='HUMAN_SOURCE_CHALLENGE_PASSED' else 1)
