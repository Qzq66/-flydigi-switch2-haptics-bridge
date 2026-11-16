"""Finite no-vibration read control; raw HID replies stay in local private storage."""
import datetime,json,pathlib,sys,time,hashlib
from config_read_trace import ReadOnlyTrace,compare_bytes,assess_reads
ROOT=pathlib.Path(__file__).absolute().parents[1];PRIVATE=ROOT/'handoff/2026-10-22/work/private'

def main():
    sys.path.insert(0,str(ROOT/'handoff/2026-10-22/work'))
    from bridge_windows import load_owner
    stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S');owner=load_owner();original=owner.safe.ro.lib;trace=ReadOnlyTrace(original);owner.safe.ro.lib=trace
    reader=None;rows=[];raw_rows=[];report=dict(status='INCOMPLETE',motor_commands=0,configuration_writes=0,pico_access=False,raw_replies_private=True)
    try:
        sel=json.loads((PRIVATE/'startup-config-selection-2026-11-15.json').read_text());snapshot=pathlib.Path(sel['current_configuration_backup'])
        if hashlib.sha256(snapshot.read_bytes()).hexdigest()!=sel['sha256']:raise ValueError('Expected backup changed')
        expected=json.loads(snapshot.read_text());reader=owner.safe.open_reader({})
        if owner.safe.digest(reader.ask(4,reply_size=16))!=expected['identity_sha256']:raise ValueError('Controller identity mismatch')
        origin=time.perf_counter()
        # No retries of a whole snapshot and no discarded first mismatch.
        for index in range(3):
            start=time.perf_counter();before=list(reader.state());comparisons={};raw={}
            for rid,label in ((1,'global'),(4,'mapping'),(5,'lighting'),(6,'motors')):
                data,summary=owner.safe.read_ram(reader,rid);raw[label]=dict(raw_hex=data.hex(),**summary);comparisons[label]=compare_bytes(bytes.fromhex(expected['ram'][label]['raw_hex']),data)
            after=list(reader.state());rows.append(dict(index=index,start_seconds=start-origin,end_seconds=time.perf_counter()-origin,state_matches=before==after==expected['state'],comparisons=comparisons));raw_rows.append(dict(state_before=before,state_after=after,ram=raw))
            if index<2:time.sleep(.2)
        report.update(assessment=assess_reads(rows),samples=rows)
        if report['assessment']['all_samples_match'] and all(r['state_matches'] for r in rows):report['status']='PASSED_NO_VIBRATION_READ_CONTROL'
    except BaseException as exc:report['error']=repr(exc)
    finally:
        if reader:reader.close()
        owner.safe.ro.lib=original;original.hid_exit()
        rawpath=PRIVATE/('config-read-control-raw-'+stamp+'.json');rawpath.write_text(json.dumps(dict(trace_events=trace.events,samples=raw_rows),indent=2),encoding='utf-8')
        report.update(trace_events=len(trace.events),captured_raw_bytes=trace.raw_bytes,raw_evidence_sha256=hashlib.sha256(rawpath.read_bytes()).hexdigest())
        out=ROOT/'docs'/('CONFIG_READ_CONTROL_'+stamp+'.json');out.write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps({k:v for k,v in report.items() if k!='samples'},indent=2));print(out)
    return 0 if report['status'].startswith('PASSED') else 1
if __name__=='__main__':raise SystemExit(main())
