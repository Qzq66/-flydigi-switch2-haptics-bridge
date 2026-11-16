"""Analyse an already stopped three-query capture, including actual RX components."""
import argparse,collections,hashlib,json,pathlib,re,subprocess,struct,time,zlib
from pcapng_experiment import packets,udp_payload
from forensic_wifi_decode import known_wifi_payload
from capture_clock import map_to_utc
ROOT=pathlib.Path(__file__).absolute().parents[1]

def receive_components(text):
    result={};component=None
    for line in text.splitlines():
        start=re.match(r'^\s*(\d+)\s+',line)
        if start:component=int(start[1])
        match=re.search(r'\b(Lower|Upper)\s+Rx\s+([\d,]+)\s+[\d,]+\s*\|\s*Tx',line)
        if match and component is not None:
            count=int(match[2].replace(',',''))
            if count:result[component]=max(result.get(component,0),count)
    return result

def reply_payload(row,expected):
    try:data=udp_payload(row)
    except ValueError:data=None
    if data is not None and hashlib.sha256(data).hexdigest() in expected:return data,'normal'
    data=known_wifi_payload(row['data'],expected)
    if data is not None:return data,'known_plaintext_wifi'
    raw=row['data']
    if len(raw)>=28 and raw[0]>>4==4 and struct.unpack_from('!H',raw,2)[0]==len(raw):
        try:data=udp_payload(dict(row,linktype=101))
        except ValueError:data=None
        if data is not None and hashlib.sha256(data).hexdigest() in expected:return data,'known_raw_ipv4'
    return None,None

def inspect(data,trace):
    expected={x['sha256']:x for x in trace['rows'] if x['direction']=='receive'}
    if len(expected)!=3:raise ValueError('Expected three unique application replies')
    seen=set();formats=collections.Counter();copies=0;bad=0;clock_deltas=[]
    for row in packets(data):
        payload,kind=reply_payload(row,expected)
        if payload is None:continue
        if row['truncated'] or row['reported_drops']:bad+=1;continue
        if len(payload)<36 or payload[:4]!=b'BHR2' or payload[4]!=2:continue
        if zlib.crc32(payload[:-4])!=struct.unpack_from('<I',payload,len(payload)-4)[0]:raise ValueError('Matched reply CRC invalid')
        h=hashlib.sha256(payload).hexdigest();delta=map_to_utc(expected[h]['at'],trace['anchors'])-row['timestamp_ns']
        if abs(delta)>5_000_000_000:raise ValueError('Timestamp epoch/units mismatch')
        seen.add(h);formats[kind]+=1;copies+=1;clock_deltas.append(delta)
    return dict(matched_reply_sequences=len(seen),all_three_observed=len(seen)==3 and not bad,
        matched_component_copies=copies,formats=dict(formats),truncated_or_drop_reported=bad,
        component_to_app_ns_range=[min(clock_deltas),max(clock_deltas)] if clock_deltas else None,
        timestamp_scope='Epoch/units sanity only; not original radio timing or precise performance calibration')

def main():
    p=argparse.ArgumentParser();p.add_argument('--run-id',required=True);a=p.parse_args()
    if not re.fullmatch(r'\d{8}-\d{6}',a.run_id):p.error('Invalid run ID')
    folder=ROOT/'handoff/2026-10-22/work/private'/('pktmon-short-selected-'+a.run_id)
    helper_path=ROOT/'docs'/('PKTMON_SHORT_SELECTED_'+a.run_id+'.json');app_path=ROOT/'docs'/('SHORT_RAM_SELECTED_'+a.run_id+'.json')
    out=ROOT/'docs'/('SHORT_RAM_SELECTED_ANALYSIS_'+a.run_id+'.json');converted=folder/'rx-components'
    if out.exists() or converted.exists():raise ValueError('Preserve previous analysis')
    report=dict(status='INCOMPLETE',hardware_access=False,capture_started=False,components=[],motor_commands=0)
    try:
        helper=json.loads(helper_path.read_text());app=json.loads(app_path.read_text())
        if helper['status']!='PKTMON_SHORT_SELECTED_ARTIFACTS_READY_NOT_YET_ANALYSED' or not helper['capture_stopped'] or not helper['filter_removed'] or helper['cleanup_errors']:raise ValueError('Capture not cleanly stopped and converted')
        if app['status']!='THREE_RAM_QUERY_REPLIES_FLASH_UNCHANGED_PENDING_CAPTURE_ANALYSIS':raise ValueError('RAM lifecycle or three replies incomplete')
        trace_data=(folder/'application-packets.json').read_bytes()
        if hashlib.sha256(trace_data).hexdigest()!=app['packet_clock']['private_trace_sha256']:raise ValueError('Application trace binding')
        trace=json.loads(trace_data)
        if trace['errors'] or trace['overflow'] or [x['direction'] for x in trace['rows']]!=['send','receive']*3:raise ValueError('Application observation incomplete')
        full=inspect((folder/'packets.pcapng').read_bytes(),trace);report['full_capture']=full
        item=next(x for x in helper['commands'] if x['tag']=='counters-after-send');raw=(folder/item['stdout_file']).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=item['stdout_sha256']:raise ValueError('RX counter source binding')
        components=receive_components(raw.decode('utf-8'))
        if not components or len(components)>64:raise ValueError('Actual RX component bounds')
        converted.mkdir();started=time.monotonic()
        for component,count in sorted(components.items()):
            if time.monotonic()-started>150:raise TimeoutError('Offline conversion total budget')
            path=converted/('component-'+str(component)+'.pcapng')
            with (converted/(str(component)+'.stdout')).open('xb') as stdout,(converted/(str(component)+'.stderr')).open('xb') as stderr:
                q=subprocess.run([r'C:\Windows\System32\PktMon.exe','etl2pcap',str(folder/('packets-'+a.run_id+'.etl')),'--component-id',str(component),'--out',str(path)],stdout=stdout,stderr=stderr,timeout=45)
            if q.returncode:raise ValueError('Offline component conversion failed')
            result=inspect(path.read_bytes(),trace);result.update(component_id=component,rx_counter_max=count,capture_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            report['components'].append(result)
        report.update(app_report_sha256=hashlib.sha256(app_path.read_bytes()).hexdigest(),helper_report_sha256=hashlib.sha256(helper_path.read_bytes()).hexdigest(),
            complete_rx_components=[x['component_id'] for x in report['components'] if x['all_three_observed']],full_flash_after_matches=app['full_flash_after_matches'])
        if full['all_three_observed'] and report['complete_rx_components']:report['status']='PASSED_THREE_QUERY_BIDIRECTIONAL_CAPTURE_AND_FLASH_UNCHANGED'
    except Exception as exc:report['error']=repr(exc)
    with out.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
    print(json.dumps(report,indent=2));return 0 if report['status'].startswith('PASSED_') else 1

if __name__=='__main__':raise SystemExit(main())
