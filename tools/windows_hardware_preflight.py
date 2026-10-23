"""Identity/configuration reads and paired timer acquire/release; no motor commands."""
import pathlib,sys,json,datetime,time
ROOT=pathlib.Path(__file__).absolute().parents[1];WORK=ROOT/'handoff/2026-10-22/work'
sys.path.insert(0,str(WORK))
from bridge_windows import load_owner,TimerResolution,XInputSource
stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
private=WORK/'private';private.mkdir(exist_ok=True)
report=dict(status='INCOMPLETE',motor_commands=0,persistent_write_commands=0,checks={})
owner=None;r=None;timer=TimerResolution()
try:
    owner=load_owner();r=owner.safe.open_reader(report)
    b=owner.backup(r,private/('hardware-preflight-backup-'+stamp+'.json'))
    report['checks']['validated_identity_and_configuration_backup']=True
    owner.verify(r,b,report)
    report['checks']['readback_matches']=report['configuration_unchanged']
    report['checks']['timer_acquired']=timer.start();timer.close();timer.close()
    report['checks']['timer_released']=not timer.active
    source=XInputSource();source()
    report['checks']['unique_xinput_source']=True;report['xinput_slot']=source.slot
    if all(report['checks'].values()):report['status']='PASSED_READONLY_PREFLIGHT'
except BaseException as e:report['error']=repr(e)
finally:
    timer.close()
    if r:r.close()
    if owner:owner.safe.ro.lib.hid_exit()
    output=ROOT/'docs'/('WINDOWS_HARDWARE_PREFLIGHT_'+stamp+'.json')
    output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2));print(str(output))
raise SystemExit(0 if report['status']=='PASSED_READONLY_PREFLIGHT' else 1)
