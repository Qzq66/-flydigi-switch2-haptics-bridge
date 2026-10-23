"""USB diagnostics and broadcast discovery on the RAM image; no Flydigi access."""
import importlib.util,json,pathlib,sys,time,datetime
ROOT=pathlib.Path(__file__).absolute().parents[1];WORK=ROOT/'handoff/2026-10-22/work';sys.path.insert(0,str(WORK))
from bridge_transport import Client
from bridge_render import collect_frames
spec=importlib.util.spec_from_file_location('probe',WORK/'test-pico-bridge-v042.py');probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)
spec=importlib.util.spec_from_file_location('live',WORK/'bridge-switch-live.py');live=importlib.util.module_from_spec(spec);spec.loader.exec_module(live)
stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S');report=dict(status='INCOMPLETE',flydigi_access=False,motor_output=False,flash_write=False);client=None
try:
    probe.open_candidate();ep=probe.endpoint(timeout=40)
    report['wifi_link_up']=True
    selection=json.loads((WORK/'private/rollback-selection.json').read_text(encoding='utf-8'))
    saved=json.loads((pathlib.Path(selection['root'])/'work/private/bridge-session.json').read_text(encoding='utf-8-sig'))
    report['session_matches_flash_launcher']=int(ep['session'],16)==int(saved['session'],16)
    report['broadcast_exact_endpoint']=live.discover(int(ep['session'],16),5)==ep['ip']
    client=Client(ep['ip'],int(ep['session'],16));replies=0;timeouts=0;until=time.perf_counter()+6
    while time.perf_counter()<until:
        if client.poll():replies+=1
        else:timeouts+=1
        time.sleep(.004)
    report.update(valid_replies=replies,poll_timeouts=timeouts)
    probe.m.send(0x80,b'\xfcENDLAB42');until=time.perf_counter()+3
    collect_frames(client,lambda f:None,lambda:time.perf_counter()>until)
    report['terminal_ack_replied']=client.terminal_ack_replied
    if report['session_matches_flash_launcher'] and report['broadcast_exact_endpoint'] and replies>0 and not timeouts and client.terminal_ack_replied:report['status']='PASSED_PC_WIFI_DISCOVERY'
except BaseException as exc:report['error']=repr(exc)
finally:
    if client:client.close()
    if probe.m.handle:
        if not (client and client.terminal_received):
            try:probe.m.send(0x80,b'\xfeRESETLAB')
            except BaseException as exc:report['reset_error']=repr(exc)
        probe.m.lib.hid_close(probe.m.handle)
    probe.m.lib.hid_exit()
    output=ROOT/'docs'/('WINDOWS_PC_DISCOVERY_'+stamp+'.json');output.write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2));print(output)
raise SystemExit(0 if report['status']=='PASSED_PC_WIFI_DISCOVERY' else 1)
