"""Diagnostic traffic only: PC initiates requests, Pico echoes tagged test words.
No controller/HID imports; no unsolicited inbound port or firewall changes.
"""
import argparse,socket,struct,zlib,time,json,pathlib,statistics,datetime
p=argparse.ArgumentParser();p.add_argument('--ip',required=True);p.add_argument('--session',required=True)
a=p.parse_args();nonce=int(a.session,16);sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
sock.bind(('192.168.137.1',0));sock.settimeout(.08)
result=dict(started_at=datetime.datetime.now().astimezone().isoformat(),traffic='diagnostic test pattern, no haptics output',
    target=a.ip,requests=300,received=0,lost=0,bad_crc=0,bad_payload=0,source_times_us=[],rtt_ms=[],local_only=False)
try:
    start=time.perf_counter()
    for seq in range(result['requests']):
        target=start+seq*.008
        if target>time.perf_counter():time.sleep(target-time.perf_counter())
        # Reanchor a late schedule instead of trying to catch up in a burst.
        if time.perf_counter()-target>.04:start=time.perf_counter()-seq*.008
        sent=time.perf_counter();sock.sendto(struct.pack('<4sIQ',b'BHP1',seq,nonce),(a.ip,49723))
        received=False
        while time.perf_counter()-sent<.08:
            try:data,peer=sock.recvfrom(512)
            except socket.timeout:break
            if peer!=(a.ip,49723) or len(data)!=40:continue
            magic,version,flags,size,session,number,stamp,payload,crc=struct.unpack('<4sBBHQIQ8sI',data)
            if zlib.crc32(data[:36])!=crc:result['bad_crc']+=1;continue
            if (magic,version,flags,size,session,number)!=(b'BHD1',1,1,40,nonce,seq):continue
            if payload!=struct.pack('<II',seq,seq^0xffffffff):result['bad_payload']+=1;continue
            result['rtt_ms'].append((time.perf_counter()-sent)*1000);result['source_times_us'].append(stamp)
            result['received']+=1;received=True;break
        if not received:result['lost']+=1
    # A different session token must not receive a response.
    sock.sendto(struct.pack('<4sIQ',b'BHP1',999,nonce^1),(a.ip,49723))
    try:sock.recvfrom(512);result['wrong_session_ignored']=False
    except socket.timeout:result['wrong_session_ignored']=True
finally:sock.close()
times=result['source_times_us'];rtts=sorted(result['rtt_ms'])
result['source_timestamps_monotonic']=all(b>a for a,b in zip(times,times[1:]))
result['rtt_summary_ms']=dict(min=min(rtts),median=statistics.median(rtts),p95=rtts[int(.95*(len(rtts)-1))],max=max(rtts)) if rtts else None
result['status']='PASSED_300_EXACT_DIAGNOSTIC_ROUNDTRIPS' if result['received']==300 and not result['bad_crc'] and not result['bad_payload'] and result['source_timestamps_monotonic'] and result['wrong_session_ignored'] else 'MEASURED_WITH_ERRORS'
path=pathlib.Path(__file__).absolute().parent.parent/'outputs'/('pico-wifi-udp-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'.json')
path.write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in ('rtt_ms','source_times_us')},indent=2));print(str(path))
raise SystemExit(0 if result['status']=='PASSED_300_EXACT_DIAGNOSTIC_ROUNDTRIPS' else 1)
