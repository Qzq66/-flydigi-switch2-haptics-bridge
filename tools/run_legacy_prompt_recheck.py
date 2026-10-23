"""Run frozen legacy notification child under a strict independent guardian."""
import datetime,json,pathlib,subprocess,sys
ROOT=pathlib.Path(__file__).absolute().parents[1];WORK=ROOT/'handoff/2026-10-22/work';sys.path.insert(0,str(WORK))
from bridge_windows import load_owner
from bridge_process import communicate_bounded,child_succeeded
stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S');private=WORK/'private'
selection=json.loads((private/'rollback-selection.json').read_text(encoding='utf-8'))
owner=load_owner();safe=owner.safe;bp=private/('legacy-recheck-backup-'+stamp+'.json');cp=private/('legacy-recheck-child-'+stamp+'.json')
report=dict(status='INCOMPLETE',firmware='retained v040',mode='retained Windows 120ms notification, +/-12',prompt_ms=120,prompt_offset=12,actual_switch_test=True,automatic_resume=False,persistent_flydigi_commands=0,guardian='strict current parent supervising frozen legacy child; no timeout accepted as success')
r=b=proc=None;dirty=False
try:
    r=safe.open_reader(report);b=owner.backup(r,bp);r.close();r=None
    args=[sys.executable,selection['entry'],'--child',str(bp),str(cp),'--prompt-ms','120','--prompt-offset','12']
    proc=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,creationflags=subprocess.CREATE_NO_WINDOW);dirty=True
    (private/'legacy-listener-ready.json').write_text(json.dumps(dict(stamp=stamp,child_pid=proc.pid,started=True)),encoding='utf-8')
    print('LISTENER_STARTED; discovery window 120 seconds; bounded notification output only',flush=True)
    stdout,stderr,killed=communicate_bounded(proc,155);report.update(child_exit=proc.returncode,guardian_killed_child=killed,child_stderr=stderr[-1500:])
    if cp.exists():report['child']=json.loads(cp.read_text(encoding='utf-8'))
    r=safe.open_reader(report);owner.identity(r,b);owner.stop(r,report);dirty=False;owner.verify(r,b,report)
    if not killed and child_succeeded(report.get('child'),proc.returncode,live=True) and report['runtime_disable_ack'] and report['configuration_unchanged']:
        report['status']='PASSED_LEGACY_LIMITED_PROMPT_PROGRAM_CHECKS'
except BaseException as exc:report['error']=repr(exc)
finally:
    if proc and proc.poll() is None:proc.kill();proc.wait(timeout=2)
    if b and dirty:
        try:
            if r is None:r=safe.open_reader(report)
            owner.identity(r,b);owner.stop(r,report);owner.verify(r,b,report)
        except BaseException as exc:report['cleanup_error']=repr(exc)
    if r:r.close()
    safe.ro.lib.hid_exit()
    output=ROOT/'docs'/('WINDOWS_LEGACY_PROMPT_RECHECK_'+stamp+'.json');output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='child'},indent=2));print(str(output))
raise SystemExit(0 if report['status']=='PASSED_LEGACY_LIMITED_PROMPT_PROGRAM_CHECKS' else 1)
