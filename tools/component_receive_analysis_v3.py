"""Offline, per-component packet-hash correlation; no network or device access."""
import collections,hashlib,statistics,struct,zlib
from capture_clock import map_to_utc
from pcapng_experiment import packets
from analyse_short_ram_path import reply_payload

def correlate(trace,capture):
    if trace['errors'] or trace['overflow']:raise ValueError('Application observer incomplete')
    receives=collections.defaultdict(list);application=[]
    for row in trace['rows']:
        if row['direction']=='receive':
            item=dict(row,index=len(application));application.append(item);receives[row['sha256']].append(item)
    seen=collections.defaultdict(list);truncated=0
    for packet in packets(capture):
        payload,_=reply_payload(packet,receives)
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
        matched.append(dict(index=row['index'],at=row['at'],component_first_ns=min(observed),component_last_ns=max(observed),
            app_ns=app,copies=len(observed),delay_ns=app-min(observed)))
    matched.sort(key=lambda x:x['at']);delays=sorted(x['delay_ns'] for x in matched)
    worst=None;adjacent_pairs=0
    for a,b in zip(matched,matched[1:]):
        if b['index']!=a['index']+1:continue
        adjacent_pairs+=1
        gap=b['app_ns']-a['app_ns']
        if worst is None or gap>worst['app_gap_ns']:
            worst=dict(application_pair_index=a['index'],app_gap_ns=gap,component_gap_ns=b['component_first_ns']-a['component_first_ns'],
                earlier_component_to_app_ns=a['delay_ns'],later_component_to_app_ns=b['delay_ns'])
    expected=len(application);bins=[dict(application=0,matched=0) for _ in range(12)]
    indexes={x['index'] for x in matched};largest=None
    if application:
        span=application[-1]['at']-application[0]['at']
        for row in application:
            bin_index=min(11,int((row['at']-application[0]['at'])/span*12)) if span>0 else 0
            bins[bin_index]['application']+=1;bins[bin_index]['matched']+=int(row['index'] in indexes)
        for a,b in zip(application,application[1:]):
            gap=b['at']-a['at']
            if gap<0:raise ValueError('Application receive order reversed')
            if largest is None or gap>largest['application_gap_seconds']:
                largest=dict(application_pair_index=a['index'],application_gap_seconds=gap,
                    both_packets_matched=a['index'] in indexes and b['index'] in indexes)

    return dict(application_receive_rows=expected,matched_receive_rows=len(matched),ambiguous_payload_groups=ambiguous,
        truncated_or_drop_reported=truncated,complete_receive_coverage=bool(expected) and len(matched)==expected and not truncated,
        component_copies=sum(x['copies'] for x in matched),negative_beyond_1ms=sum(x < -1_000_000 for x in delays),
        component_to_application_ns=dict(min=min(delays),median=statistics.median(delays),p95=delays[int((len(delays)-1)*.95)],max=max(delays)) if delays else None,
        matched_original_adjacent_pairs=adjacent_pairs,largest_matched_original_adjacent_gap=worst,
        largest_original_application_gap=largest,coverage_12_time_bins=bins,
        scope='Per-component observation to socket return; includes OS queues and scheduling. Not physical radio arrival or one-way Pico/PC clock synchronization.')
