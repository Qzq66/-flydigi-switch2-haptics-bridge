"""Compare manual XInput liveness around existing read-only configuration queries."""
import datetime,json,pathlib,subprocess,sys
ROOT=pathlib.Path(__file__).absolute().parents[1];PRIVATE=ROOT/'handoff/2026-10-22/work/private'
sys.path.insert(0,str(ROOT/'handoff/2026-10-22/work'))
sys.path.insert(0,str(ROOT/'tools'))
def main():
    from bridge_process import communicate_bounded
    from bridge_windows import load_owner
    from game_input_liveness import passed
    stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S');report=dict(status='INCOMPLETE',motor_commands=0,configuration_writes=0,pico_access=False)
    owner=reader=None
    def gate(name):
        f=PRIVATE/('read-retention-'+name+'-'+stamp+'.json')
        print('MANUAL_INPUT_CHECK_'+name.upper(),flush=True)
        proc=subprocess.Popen([sys.executable,'-B',str(ROOT/'tools/game_input_liveness.py'),str(f)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
        _,_,killed=communicate_bounded(proc,55)
        d=json.loads(f.read_text()) if f.exists() else {}
        report[name]=d
        if killed or proc.returncode or not passed(d):raise ValueError(name+' manual input check failed')
    try:
        gate('before_read_queries')
        owner=load_owner();reader=owner.safe.open_reader({})
        backup=owner.backup(reader,PRIVATE/('read-retention-backup-'+stamp+'.json'))
        owner.verify(reader,backup,report)
        if not report.get('configuration_unchanged'):raise ValueError('Read-only comparison mismatch')
        reader.close();reader=None;owner.safe.ro.lib.hid_exit();owner=None
        gate('after_read_queries')
        report['status']='PASSED_MANUAL_INPUT_BEFORE_AND_AFTER_READONLY_QUERIES'
    except BaseException as exc:report['error']=repr(exc)
    finally:
        if reader:reader.close()
        if owner:owner.safe.ro.lib.hid_exit()
        out=ROOT/'docs'/('READONLY_INPUT_RETENTION_'+stamp+'.json')
        with out.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
        print(json.dumps({k:v for k,v in report.items() if k not in ('before_read_queries','after_read_queries')},indent=2));print(out)
    return 0 if report['status'].startswith('PASSED_') else 1
if __name__=='__main__':raise SystemExit(main())
