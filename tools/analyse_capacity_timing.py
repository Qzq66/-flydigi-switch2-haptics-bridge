"""Offline timing decomposition, bound to captured payload hashes; no device access."""
import hashlib,json,math,pathlib,struct
from collections import defaultdict
from capture_clock import map_to_utc
from pcapng_experiment import packets,udp_payload

ROOT=pathlib.Path(__file__).resolve().parents[1]
TAG='20261026-221119'

def stats(values):
    v=sorted(values)
    if not v:return {'count':0}
    return dict(count=len(v),minimum_ms=v[0]/1e6,median_ms=v[len(v)//2]/1e6,
                p95_ms=v[math.ceil(.95*len(v))-1]/1e6,p99_ms=v[math.ceil(.99*len(v))-1]/1e6,
                maximum_ms=v[-1]/1e6,over_12ms=sum(x>12e6 for x in v),over_80ms=sum(x>80e6 for x in v))

def main():
    folder=ROOT/'handoff/2026-10-22/work/private'/('pktmon-ram-capacity-'+TAG)
    trace_bytes=(folder/'application-packets.json').read_bytes();trace=json.loads(trace_bytes)
    app=json.loads((ROOT/'docs'/('RAM_CAPACITY_PATH_'+TAG+'.json')).read_text())
    assert hashlib.sha256(trace_bytes).hexdigest()==app['packet_clock']['private_trace_sha256']
    assert not trace['errors'] and not trace['overflow']
    by_hash={r['sha256']:r for r in trace['rows']}
    assert len(by_hash)==len(trace['rows'])
    capture_path=folder/'rx-components/component-124.pcapng'
    captured=defaultdict(list);payloads={}
    for packet in packets(capture_path.read_bytes()):
        if packet['truncated'] or packet['reported_drops']:raise ValueError('Incomplete packet')
        try:payload=udp_payload(packet)
        except ValueError:continue
        if payload is None:continue
        h=hashlib.sha256(payload).hexdigest()
        if h in by_hash:captured[h].append(packet['timestamp_ns']);payloads[h]=payload
    assert set(payloads)==set(by_hash),'Require complete send and receive capture'
    requests={};replies=[]
    for h,row in by_hash.items():
        data=payloads[h];item=dict(app=map_to_utc(row['at'],trace['anchors']),kernel=min(captured[h]))
        if row['direction']=='send':
            assert len(data)==20 and data[:4]==b'BHP2'
            key=struct.unpack_from('<I',data,4)[0];assert key not in requests
            requests[key]=item
        else:
            assert len(data)==36 and data[:4]==b'BHR2'
            key,boot,source=struct.unpack_from('<III',data,16)
            item.update(key=key,boot=boot,source=source);replies.append(item)
    replies.sort(key=lambda r:r['app']);assert len(replies)==len(requests)==1943
    for r in replies:r['request']=requests[r['key']]
    rtt=[r['app']-r['request']['app'] for r in replies]
    outbound=[r['request']['kernel']-r['request']['app'] for r in replies]
    outside=[r['kernel']-r['request']['kernel'] for r in replies]
    inbound=[r['app']-r['kernel'] for r in replies]
    assert all(abs(rtt[i]-outbound[i]-outside[i]-inbound[i])<=1 for i in range(len(rtt)))
    gaps=[]
    for i,(a,b) in enumerate(zip(replies,replies[1:])):
        gaps.append(dict(pair_index=i,receive_gap_ms=(b['app']-a['app'])/1e6,
          send_gap_ms=(b['request']['app']-a['request']['app'])/1e6,
          earlier_round_trip_ms=rtt[i]/1e6,later_round_trip_ms=rtt[i+1]/1e6,
          later_app_send_to_component_ms=outbound[i+1]/1e6,
          later_component_round_trip_ms=outside[i+1]/1e6,
          later_component_to_app_ms=inbound[i+1]/1e6,
          source_gap_ms=((b['source']-a['source'])&0xffffffff)/1000 if a['boot']==b['boot'] else None,
          request_distance=(b['key']-a['key'])&0xffffffff))
    report=dict(status='COMPLETE_OFFLINE_TIMING_DECOMPOSITION',hardware_access=False,motor_commands=0,
      sample_count=len(replies),component_id=124,private_trace_sha256=hashlib.sha256(trace_bytes).hexdigest(),
      capture_sha256=hashlib.sha256(capture_path.read_bytes()).hexdigest(),
      application_round_trip=stats(rtt),app_send_to_component=stats(outbound),
      component_round_trip=stats(outside),component_to_app_receive=stats(inbound),
      application_receive_intervals=stats([round(g['receive_gap_ms']*1e6) for g in gaps]),
      original_request_send_intervals=stats([round(g['send_gap_ms']*1e6) for g in gaps]),
      largest_receive_gaps=sorted(gaps,key=lambda g:g['receive_gap_ms'],reverse=True)[:10],
      negative_send_to_component_over_1ms=sum(x < -1e6 for x in outbound),
      negative_component_to_receive_over_1ms=sum(x < -1e6 for x in inbound),
      limitations=['Component timestamp is a Windows observation point, not radio transmission time.',
      'Component round trip includes outbound path, Pico processing and inbound path; cannot isolate Wi-Fi.',
      'Application send observation occurs after sendto, so its delta is not syscall duration.',
      'PC/Pico absolute clocks are not synchronised; source_us used only for intervals.',
      'An idle RAM window does not validate gameplay or native haptic fidelity.'])
    out=ROOT/'docs'/('RAM_CAPACITY_TIMING_'+TAG+'.json')
    with out.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
