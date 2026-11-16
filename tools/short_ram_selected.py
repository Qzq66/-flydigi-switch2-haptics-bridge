"""Three-query RAM-only path diagnostic. Device access only with --play."""
import argparse,datetime,hashlib,json,pathlib,re,struct,subprocess,sys,time
ROOT=pathlib.Path(__file__).absolute().parents[1]
WORK=ROOT/'handoff/2026-10-22/work';PRIVATE=WORK/'private'
RAM=ROOT/'build/pico-v043-120s-ram-snapshot/pico_pro_capture.uf2'
RAM_SHA='49acbba65eea98c1ec29a18e697c33f364111a0b2a224f56bb792067c1ce8c56'

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def sram_bounds(data):
    if not data or len(data)%512:raise ValueError('UF2 block length')
    low=0x20082000;high=0;indexes=set();total=len(data)//512
    for at in range(0,len(data),512):
        a,b,flags,address,size,index,count,family=struct.unpack_from('<8I',data,at)
        if a!=0x0a324655 or b!=0x9e5d5157 or struct.unpack_from('<I',data,at+508)[0]!=0x0ab16f30:raise ValueError('UF2 identity')
        if not 0<size<=476 or not 0x20000000<=address<address+size<=0x20082000:raise ValueError('Non-SRAM target')
        if count!=total or index in indexes or index>=count:raise ValueError('UF2 numbering')
        indexes.add(index);low=min(low,address);high=max(high,address+size)
    return dict(blocks=total,minimum_address=hex(low),maximum_end=hex(high))

def three_queries(sock,peer,session,pause=time.sleep):
    sys.path.insert(0,str(WORK));from bridge_protocol import unpack
    summaries=[]
    for i in range(3):
        request=0x4c410001+i
        data=struct.pack('<4sIQI',b'BHP2',request,session,0xffffffff)
        if sock.sendto(data,peer)!=20:raise ValueError('Partial diagnostic send')
        response,address=sock.recvfrom(512)
        if address!=peer:raise ValueError('Unexpected diagnostic peer; no retry')
        frame=unpack(response,session,request)
        if frame['events']:raise ValueError('Unexpected upstream fields in an idle RAM fixture')
        summaries.append(dict(sequence=i,reply_crc_valid=True,empty_upstream=True))
        if i<2:pause(.25)
    return summaries

def build_plan():
    if digest(RAM)!=RAM_SHA:raise ValueError('Reviewed RAM UF2 changed')
    bounds=sram_bounds(RAM.read_bytes());manifest=json.loads(RAM.with_suffix('.manifest.json').read_text())
    if manifest['profile']!='ram' or manifest['sha256']!=RAM_SHA:raise ValueError('RAM manifest')
    ready=[]
    for path in (ROOT/'docs').glob('V043_READY_BASELINE_*.json'):
        b=json.loads(path.read_text())
        if b.get('baseline_generation')==37:ready.append((path,b))
    if len(ready)!=1 or ready[0][1].get('physical_full_readback_verified') is not True:raise ValueError('Verified37 baseline required')
    path,baseline=ready[0]
    reference=ROOT/'docs/SHORT_RAM_PATH_ASSESSMENT_20261026-211652.json'
    evidence=json.loads(reference.read_text())
    if evidence.get('status')!='PASSED_SHORT_RAM_THREE_QUERY_CAPTURE_CLEANUP_AND_FULL_FLASH_COMPARISON' or not all(evidence['checks'].values()):raise ValueError('Successful all-component three-query reference required')
    names=('short_ram_selected.py','packet_clock_probe.py','capture_clock.py','pico_v043_probe.py','run_pktmon_short_selected.ps1','pktmon_capture_common_v4.ps1')
    return dict(kind='same_three_RAM_queries_explicit_component_comparison',reference_sha256=digest(reference),baseline_generation=37,
        expected_full_flash_sha256=baseline['full_flash_sha256'],firmware_sha256=baseline['firmware_sha256'],
        baseline_proof_sha256=digest(path),ram_sha256=RAM_SHA,ram_bounds=bounds,queries=3,retries=0,
        receive_timeout_seconds=.5,request_spacing_seconds=.25,maximum_capture_seconds=180,
        motor_commands=0,flydigi_access=False,flash_write=False,switch_required=False,
        source_sha256={n:digest(ROOT/'tools'/n) for n in names})

def play(plan_path,folder,picotool,nm):
    import socket
    sys.path.insert(0,str(WORK))
    from pico_v043_probe import Probe
    from v043_installation import verify_installed
    from packet_clock_probe import PacketClockProbe,PacketClockSocket
    from capture_clock import precise_utc_reader
    plan=json.loads(plan_path.read_text());folder=folder.resolve()
    if plan!=build_plan():raise ValueError('Short diagnostic plan/source mismatch')
    if folder.parent!=PRIVATE.resolve() or not folder.name.startswith('pktmon-short-selected-'):raise ValueError('Expected owned capture directory')
    if not (folder/'capture-ready.json').exists():raise ValueError('Capture not ready')
    helper_report=ROOT/'docs'/('PKTMON_SHORT_SELECTED_'+folder.name.removeprefix('pktmon-short-selected-')+'.json')
    if helper_report.exists() or (folder/'stop-requested.flag').exists():raise ValueError('Capture already ended; do not load RAM')
    out=ROOT/'docs'/('SHORT_RAM_SELECTED_'+folder.name.removeprefix('pktmon-short-selected-')+'.json')
    if out.exists():raise ValueError('Keep previous evidence')
    record_path=pathlib.Path(json.loads((PRIVATE/'v043-install-selection.json').read_text())['record']);record=json.loads(record_path.read_text())
    report=dict(status='INCOMPLETE',motor_commands=0,flydigi_access=False,flash_write=False,queries_sent_limit=3,
        ram_loaded=False,full_flash_after_matches=False,cleanup_errors=[],plan_sha256=digest(plan_path))
    probe=observer=sock=None;loaded=False
    def clean_error(exc):return re.sub(r'\b(?:\d{1,3}\.){3}\d{1,3}\b','[private address]',repr(exc)).replace(record['pico_serial'],'[private board]')
    def tool(args):
        with (folder/'picotool-private.txt').open('a',encoding='utf-8') as log:
            q=subprocess.run([str(picotool),*map(str,args),'--ser',record['pico_serial']],stdout=log,stderr=subprocess.STDOUT,timeout=30)
        return q.returncode==0
    try:
        hotspot=json.loads(subprocess.check_output(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(ROOT/'tools/read_hotspot_state.ps1')],text=True,timeout=20))
        if hotspot.get('hotspot_state')!='On' or hotspot.get('band')!='TwoPointFourGigahertz' or not hotspot.get('iphone_usb_source'):raise ValueError('Existing iPhone USB / 2.4GHz hotspot required')
        steam=subprocess.run(['powershell.exe','-NoProfile','-Command',"if(@(Get-Process Steam -ErrorAction SilentlyContinue).Count){exit 1}"],capture_output=True,timeout=10)
        if steam.returncode:raise ValueError('Exit Steam before RAM diagnostic')
        report['hotspot_preflight']=hotspot;report['steam_exited']=True
        v=verify_installed(record_path,picotool,record['pico_serial'])
        if v['baseline_generation']!=37 or v['installed_snapshot_sha256']!=plan['expected_full_flash_sha256']:raise ValueError('Actual37 baseline mismatch')
        report['full_flash_before_matches']=True
        symbols=subprocess.check_output([str(nm),'-S',str(RAM.with_suffix('.elf'))],timeout=10,text=True)
        if any(x.split()[-1] in ('flash_range_program','flash_range_erase') for x in symbols.splitlines() if x.split()):raise ValueError('Flash writer symbol in RAM image')
        report['no_flash_writer_symbols']=True
        loaded=True
        if not tool(['load','-v','-x',RAM,'-t','uf2']):raise ValueError('RAM-only load failed')
        report['ram_loaded']=True;probe=Probe();probe.open('ram');endpoint=probe.endpoint()
        selection=json.loads((PRIVATE/'rollback-selection.json').read_text());saved=json.loads((pathlib.Path(selection['root'])/'work/private/bridge-session.json').read_text(encoding='utf-8-sig'))
        if endpoint['session']!=int(saved['session'],16):raise ValueError('RAM network session differs')
        observer=PacketClockProbe(precise_utc_reader(),limit=6)
        raw=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);raw.bind(('192.168.137.1',0));raw.settimeout(.5)
        sock=PacketClockSocket(raw,observer)
        report['queries']=three_queries(sock,(endpoint['ip'],49724),endpoint['session'])
    except BaseException as exc:report['error']=clean_error(exc)
    finally:
        if sock:
            try:sock.close()
            except Exception as exc:report['cleanup_errors'].append(clean_error(exc))
        if observer:
            try:report['packet_clock']=observer.finish(folder/'application-packets.json')
            except Exception as exc:report['cleanup_errors'].append(clean_error(exc))
        (folder/'stop-requested.flag').write_text('three-query diagnostic finished')
        if probe:
            try:
                if probe.m.handle and probe.m.verified:
                    probe.m.send(0x80,b'\xfeRESETLAB');report['ram_reset_requested']=True;time.sleep(.35)
            except Exception as exc:report['cleanup_errors'].append(clean_error(exc))
            finally:
                try:probe.close()
                except Exception as exc:report['cleanup_errors'].append(clean_error(exc))
        if loaded:
            try:
                from fidelity_network_io import wait_full_flash
                report['bootsel_verify']=wait_full_flash(lambda:tool(['verify',record['installed_snapshot'],'-t','bin','-o','0x10000000']),timeout=30)
                report['full_flash_after_matches']=report['bootsel_verify']['matched']
            except Exception as exc:report['cleanup_errors'].append(clean_error(exc))
        if (len(report.get('queries',[]))==3 and report.get('ram_reset_requested') and report['full_flash_after_matches']
            and not report.get('error') and not report['cleanup_errors']):report['status']='THREE_RAM_QUERY_REPLIES_FLASH_UNCHANGED_PENDING_CAPTURE_ANALYSIS'
        with out.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
        print(json.dumps(report,indent=2))
    return 0 if report['status'].startswith('THREE_RAM_QUERY_') else 1

def main():
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--prepare',type=pathlib.Path);g.add_argument('--play',type=pathlib.Path)
    p.add_argument('--capture-directory',type=pathlib.Path);p.add_argument('--picotool',type=pathlib.Path);p.add_argument('--nm',type=pathlib.Path);a=p.parse_args()
    if a.prepare:
        if a.prepare.exists():raise ValueError('Keep immutable plan')
        a.prepare.write_text(json.dumps(build_plan(),indent=2)+'\n');return 0
    if not all((a.capture_directory,a.picotool,a.nm)):p.error('--play requires capture directory, picotool and nm')
    return play(a.play,a.capture_directory,a.picotool,a.nm)

if __name__=='__main__':raise SystemExit(main())
