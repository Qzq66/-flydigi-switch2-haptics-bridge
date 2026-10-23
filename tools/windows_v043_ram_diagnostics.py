"""Load exact reviewed RAM image; no Flydigi access; verify Flash before/after."""
import argparse,ctypes as C,datetime,hashlib,importlib.util,json,pathlib,struct,subprocess,sys,time
ROOT=pathlib.Path(__file__).absolute().parents[1];WORK=ROOT/'handoff/2026-10-22/work';sys.path.insert(0,str(WORK))
from pico_v043_probe import Probe
from bridge_transport import Client
from bridge_input import NEUTRAL
from bridge_windows import TimerResolution
from pico_continuous_log import CAPACITY,decode_sector

p=argparse.ArgumentParser(description=__doc__)
for name in ('picotool','nm','image','elf','baseline'):p.add_argument('--'+name,type=pathlib.Path,required=True)
p.add_argument('--pico-serial',required=True);p.add_argument('--expected-sha256',required=True);p.add_argument('--case',choices=('lifecycle','capacity'),required=True);a=p.parse_args()
stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S');private=WORK/'private'
report=dict(status='INCOMPLETE',case=a.case,flydigi_access=False,physical_output=False,flash_write=False,ram_image_sha256=a.expected_sha256.lower(),checks={})
probe=client=None;timer=TimerResolution();events=[];expected=[];failure=None
console=private/('v043-ram-'+a.case+'-'+stamp+'-console.txt');raw=private/('v043-ram-'+a.case+'-'+stamp+'.bin')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def tool(label,args,required=True):
    with console.open('a',encoding='utf-8') as h:
        h.write(label+'\n');h.flush()
        try:result=subprocess.run([str(a.picotool),*map(str,args),'--ser',a.pico_serial],stdout=h,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW,timeout=25)
        except subprocess.TimeoutExpired:raise RuntimeError(label+' timed out; see private console') from None
    if required and result.returncode:raise RuntimeError(label+' failed; see private console')
    return result.returncode==0
def require(name,condition):
    report['checks'][name]=bool(condition)
    if not condition:raise ValueError(name)
try:
    require('reviewed_ram_image',sha(a.image)==a.expected_sha256.lower())
    manifest=json.loads(a.image.with_suffix('.manifest.json').read_text())
    require('ram_bounds',manifest['profile']=='ram' and manifest['sha256']==a.expected_sha256.lower() and int(manifest['minimum_address'],16)>=0x20000000 and int(manifest['maximum_end'],16)<=0x20082000)
    symbols=subprocess.check_output([str(a.nm),'-S',str(a.elf)],text=True)
    require('no_flash_mutation_symbols',not any(line.split()[-1] in ('flash_range_program','flash_range_erase') for line in symbols.splitlines() if line.split()))
    locations=[line.split() for line in symbols.splitlines() if line.split() and line.split()[-1]=='image']
    require('unique_ram_journal_symbol',len(locations)==1 and int(locations[0][1],16)==65536)
    address=int(locations[0][0],16);require('journal_in_sram',0x20000000<=address and address+65536<=0x20082000)
    saved=json.loads((ROOT/'docs/STAGED_GAME_BASELINE_2026-10-23.json').read_text(encoding='utf-8'))
    require('complete_baseline_hash',a.baseline.stat().st_size==4194304 and sha(a.baseline)==saved['current_full_flash_sha256'])
    tool('Verify complete Flash before RAM load',['verify',a.baseline,'-t','bin','-o','0x10000000']);report['checks']['flash_before_matches']=True
    tool('Load and execute SRAM only',['load','-v','-x',a.image,'-t','uf2'])
    probe=Probe();probe.open();report['checks']['exact_043_initial_ram_identity']=True;ep=probe.endpoint()
    selection=json.loads((private/'rollback-selection.json').read_text(encoding='utf-8'));session=json.loads((pathlib.Path(selection['root'])/'work/private/bridge-session.json').read_text(encoding='utf-8-sig'))
    require('session_matches_existing_network',ep['session']==int(session['session'],16))
    spec=importlib.util.spec_from_file_location('live_discovery',WORK/'bridge-switch-live.py');live=importlib.util.module_from_spec(spec);spec.loader.exec_module(live)
    require('broadcast_discovery',live.discover(ep['session'],5)==ep['ip'])
    m=probe.m;m.send(0x80,b'\4');m.sub(3,b'\x30');m.sub(0x40,b'\2')
    m.send(0x80,b'\xfdSNAPLOG5');header=m.read_range(0xa000,128);initial=struct.unpack_from('<I',header,24)[0]
    require('small_initial_journal',0<initial<16)
    records=m.read_range(0xa080,initial*24)
    expected=[records[i*24+12:i*24+20].hex() for i in range(initial) if records[i*24+20]&1]
    client=Client(ep['ip'],ep['session'],input_source=lambda:NEUTRAL)
    require('timer_acquired',timer.start());start=time.perf_counter();sent=0;extra=0;milestones=[];next_send=start;next_mark=30
    remaining=CAPACITY-initial;complete=False;first_source=last_source=None;input_updates=[];draining=False
    while time.perf_counter()-start<(130 if a.case=='lifecycle' else 90):
        frame=client.poll();now=time.perf_counter();elapsed=now-start
        if frame:
            first_source=frame['source_us'] if first_source is None else first_source;last_source=frame['source_us']
            events.extend(dict(sequence=e['sequence'],at_us=e['at_us'],motors=e['motors'].hex()) for e in frame['events'])
            if frame['flags']&16:
                client.confirm_end();complete=client.terminal_ack_replied;break
            draining=draining or bool(frame['flags']&8)
        if draining:
            time.sleep(.001);continue
        if a.case=='capacity' and sent<remaining and now>=next_send:
            motors=struct.pack('<II',sent,~sent&0xffffffff);m.send(0x10,bytes([sent%16])+motors)
            expected.append(motors.hex());sent+=1;next_send=now+.004
            if sent==remaining:
                for j in range(16):
                    try:m.send(0x10,b'\0'+b'\x55'*8);extra+=1
                    except OSError:break
        elif a.case=='lifecycle' and now>=next_send:
            m.send(0x10,b'\0'+bytes.fromhex('0001404000014040'));expected.append('0001404000014040');sent+=1;next_send=now+1
        if a.case=='lifecycle' and elapsed>=next_mark:
            updates=struct.unpack('<I',m.read_range(0x9238,4))[0];m.receive(0x30)
            input_updates.append(updates);milestones.append(round(elapsed,2));print(json.dumps(dict(case=a.case,elapsed_seconds=round(elapsed,1),valid_input_updates=updates)),flush=True)
            next_mark=65 if next_mark==30 else (100 if next_mark==65 else (115 if next_mark==100 else 999))
        time.sleep(.001)
    report.update(elapsed_seconds=time.perf_counter()-start,sent_injected_words=sent,extra_write_completions_after_full=extra,usb_input_milestones_seconds=milestones,input_updates=input_updates,received_events=events)
    require('terminal_acknowledged',complete and client.terminal_received and client.terminal_ack_replied)
    require('wire_sequence_contiguous',[e['sequence'] for e in events]==list(range(len(events))))
    require('all_expected_words_exact',[e['motors'] for e in events]==expected)
    if a.case=='lifecycle':
        require('live_near_120_seconds',117<=report['elapsed_seconds']<=123)
        require('usb_and_input_relay_after_115_seconds',len(milestones)==4 and milestones[-1]>=115 and all(b>a for a,b in zip(input_updates,input_updates[1:])))
    else:require('capacity_reached',sent==remaining)
except BaseException as exc:failure=type(exc).__name__+': '+str(exc);report['error']=failure
finally:
    if client:client.close()
    timer.close();report['timer_released']=not timer.active
    try:
        if not (probe and client and client.terminal_ack_replied):raise RuntimeError('No confirmed terminal session for snapshot read')
        until=time.monotonic()+5
        while True:
            try:
                if probe.m.read_virtual(0x9280,8)==b'SNAP043\1':break
            except (OSError,TimeoutError,AssertionError):pass
            if time.monotonic()>until:raise RuntimeError('Read-only RAM snapshot phase unavailable')
            time.sleep(.1)
        # The read-only phase must not ACK mode changes or expose other banks.
        m=probe.m
        m.send(0x10,b'\0'+b'\x55'*8)
        m.send(1,b'\0'+bytes.fromhex('0001404000014040')+b'\x03\x30')
        m.send(1,b'\0'+bytes.fromhex('0001404000014040')+b'\x10'+struct.pack('<IB',0x9000,8))
        reply=C.create_string_buffer(64)
        require('snapshot_rejects_normal_commands',m.lib.hid_read_timeout(m.handle,reply,64,100)==0)
        buffer=b'';read_started=time.perf_counter();last_progress=0
        try:
            while len(buffer)<65536:
                buffer+=probe.m.read_virtual(0xa000+len(buffer),min(29,65536-len(buffer)))
                if len(buffer)//16384>last_progress:
                    last_progress=len(buffer)//16384;print(json.dumps(dict(snapshot_bytes_read=len(buffer),snapshot_seconds=round(time.perf_counter()-read_started,1))),flush=True)
        finally:report.update(snapshot_bytes_read=len(buffer),snapshot_read_seconds=time.perf_counter()-read_started)
        raw.write_bytes(buffer)
        capture=decode_sector(raw.read_bytes());report['capture']={k:v for k,v in capture.items() if k!='events'}
        local=[e['motors_hex'] for e in capture['events'] if e['motors_hex'] is not None]
        require('retained_journal_crc_complete',capture['crc_valid'] and capture['complete'] and capture['no_flash_marker']==1)
        require('ram_journal_matches_wire',local==[e['motors'] for e in events])
        require('retained_END2_confirmed',capture['stream_end']=='client_confirmed')
        require('expected_end_reason',capture['reason']==('RAM_dry_run' if a.case=='lifecycle' else 'capacity_limit'))
        if a.case=='capacity':require('last_record_present_no_extra',capture['total_events']==CAPACITY and capture['events'][-1]['motors_hex']==expected[-1])
    except BaseException as exc:report['ram_readback_error']=type(exc).__name__+': '+str(exc)
    if probe:
        if probe.m.verified:
            try:probe.m.send(0x80,b'\xfeRESETLAB')
            except BaseException:report['ram_reset_requested_but_not_confirmed']=True
        probe.close()
    try:
        time.sleep(.5);until=time.monotonic()+8
        while not tool('Verify complete Flash after RAM diagnostic',['verify',a.baseline,'-t','bin','-o','0x10000000'],required=False):
            if time.monotonic()>until:raise RuntimeError('Complete Flash after diagnostic unavailable or changed')
            time.sleep(.25)
        report['checks']['flash_after_matches']=True
    except BaseException as exc:report['flash_verify_error']=type(exc).__name__+': '+str(exc)
    if not any(report.get(k) for k in ('error','ram_readback_error','flash_verify_error')) and all(report['checks'].values()) and report['timer_released']:report['status']='PASSED_V043_RAM_'+a.case.upper()
    output=ROOT/'docs'/('V043_RAM_'+a.case.upper()+'_'+stamp+'.json');output.write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in report.items() if k!='received_events'},indent=2));print(output)
raise SystemExit(0 if report['status'].startswith('PASSED_') else 1)
