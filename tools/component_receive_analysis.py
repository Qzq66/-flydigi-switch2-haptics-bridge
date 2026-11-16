"""Offline, per-component packet-hash correlation; no network or device access."""
import collections,hashlib,statistics,struct,zlib
from capture_clock import map_to_utc
from pcapng_experiment import packets,udp_payload

def correlate(trace,capture):
    if trace['errors'] or trace['overflow']:raise ValueError('Application observer incomplete')
    receives=collections.defaultdict(list)
    for row in trace['rows']:
        if row['direction']=='receive':receives[row['sha256']].append(row)
    seen=collections.defaultdict(list);truncated=0
    for packet in packets(capture):
        payload=udp_payload(packet)
        if payload is None or payload[:4]!=b'BHR2':continue
        if packet['truncated'] or packet['reported_drops']:truncated+=1;continue
        if len(payload)<36 or payload[4]!=2:continue
        count=struct.unpack_from('<H',payload,28)[0]
        if count>8 or len(payload)!=36+count*16 or struct.unpack_from('<H',payload,6)[0]!=len(payload):continue
        if struct.unpack_from('<I',payload,len(payload)-4)[0]!=zlib.crc32(payload[:-4]):continue
        h=hashlib.sha256(payload).hexdigest()
        if h in receives:seen[h].append(packet['timestamp_ns'])
    ambiguous=sum(len(rows)!=1 for rows in receives.values());matched=[]
    for h,rows in receives.items():
        if len(rows)!=1 or not seen[h]:continue
        row=rows[0];app=map_to_utc(row['at'],trace['anchors']);observed=seen[h]
        matched.append(dict(at=row['at'],component_first_ns=min(observed),component_last_ns=max(observed),
            app_ns=app,copies=len(observed),delay_ns=app-min(observed)))
    matched.sort(key=lambda x:x['at']);delays=sorted(x['delay_ns'] for x in matched)
    worst=None
    for a,b in zip(matched,matched[1:]):
        gap=b['app_ns']-a['app_ns']
        if worst is None or gap>worst['app_gap_ns']:
            worst=dict(app_gap_ns=gap,component_gap_ns=b['component_first_ns']-a['component_first_ns'],
                earlier_component_to_app_ns=a['delay_ns'],later_component_to_app_ns=b['delay_ns'])
    expected=sum(len(x) for x in receives.values())
    return dict(application_receive_rows=expected,matched_receive_rows=len(matched),ambiguous_payload_groups=ambiguous,
        truncated_or_drop_reported=truncated,complete_receive_coverage=bool(expected) and len(matched)==expected and not truncated,
        component_copies=sum(x['copies'] for x in matched),negative_beyond_1ms=sum(x < -1_000_000 for x in delays),
        component_to_application_ns=dict(min=min(delays),median=statistics.median(delays),p95=delays[int((len(delays)-1)*.95)],max=max(delays)) if delays else None,
        largest_matched_application_gap=worst,
        scope='Per-component observation to socket return; includes OS queues and scheduling. Not physical radio arrival or one-way Pico/PC clock synchronization.')
