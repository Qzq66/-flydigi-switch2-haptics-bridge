"""Replay existing evidence only. Raw packet/address data never leaves private."""
import collections,hashlib,json,pathlib,struct
from pcapng_experiment import packets,udp_payload
from forensic_wifi_decode import known_wifi_payload
ROOT=pathlib.Path(__file__).absolute().parents[1]

def inspect(path,expected):
    normal=set();wifi=set();counts=collections.Counter()
    for row in packets(path.read_bytes()):
        counts['records']+=1
        try:data=udp_payload(row)
        except ValueError:data=None;counts['normal_decode_rejected']+=1
        if data is not None:
            counts['normal_udp_records']+=1
            if data[:4]==b'BHR2':
                h=hashlib.sha256(data).hexdigest()
                if h in expected:normal.add(h)
        else:
            data=known_wifi_payload(row['data'],expected)
            if data is not None:counts['known_wifi_reply_records']+=1;wifi.add(hashlib.sha256(data).hexdigest())
    return dict(sha256=hashlib.sha256(path.read_bytes()).hexdigest(),counts=dict(counts),
        expected_application_hashes=len(expected),normal_reply_hashes=len(normal),wifi_reply_hashes=len(wifi),
        combined_reply_hashes=len(normal|wifi),full_unique_hash_coverage=bool(expected) and normal|wifi==expected)

def main():
    out=ROOT/'docs/RECEIVE_PATH_OFFLINE_20261026.json'
    if out.exists():raise ValueError('Keep original assessment')
    base=ROOT/'handoff/2026-10-22/work/private';report=dict(status='OFFLINE_REPLAY_COMPLETE_RX_CAUSE_UNRESOLVED',
        hardware_access=False,capture_started=False,filters_changed=False,network_settings_changed=False,motor_commands=0,
        current_generation_last_physically_verified=36,root_cause_proven=False,trials=[])
    for folder,sub,names in [
        ('pktmon-passive-g31-20261025-220337','offline-conversion',['packets.pcapng','component-3.pcapng','component-16.pcapng','component-35.pcapng','component-133.pcapng']),
        ('pktmon-passive-g35-20261026-202153','',['packets.pcapng','component-20.pcapng','component-124.pcapng'])]:
        p=base/folder;trace_data=(p/'application-packets.json').read_bytes();trace=json.loads(trace_data)
        expected={x['sha256'] for x in trace['rows'] if x['direction']=='receive'}
        trial=dict(trial=folder,application_receive_rows=sum(x['direction']=='receive' for x in trace['rows']),
            private_trace_sha256=hashlib.sha256(trace_data).hexdigest(),files={})
        for name in names:trial['files'][name]=inspect(p/sub/name,expected)
        report['trials'].append(trial)
    # Existing dropped records may have raw IPv4 contents despite the link label.
    p=base/'pktmon-passive-g35-20261026-202153/drops.pcapng';counts=collections.Counter()
    for row in packets(p.read_bytes()):
        d=row['data']
        if len(d)<28 or d[0]>>4!=4 or struct.unpack_from('!H',d,2)[0]!=len(d):continue
        try:data=udp_payload(dict(row,linktype=101))
        except ValueError:continue
        if data is not None:counts[data[:4].decode('ascii',errors='replace')]+=1
    report['current_dropped_raw_ipv4_prefix_counts']=dict(counts)
    report['limitations']='Known-hash forensic decoding does not change bridge acceptance or prove capture completeness. Dropped-file records do not account for every counter. Two-variable prior capture cannot isolate the IP filter from component selection.'
    report['source_sha256']={n:hashlib.sha256((ROOT/'tools'/n).read_bytes()).hexdigest() for n in ('audit_receive_path_offline.py','forensic_wifi_decode.py','test_forensic_wifi_decode.py')}
    with out.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
    print(json.dumps(dict(status=report['status'],prior_combined=report['trials'][0]['files']['packets.pcapng']['combined_reply_hashes'],
        current_combined=report['trials'][1]['files']['packets.pcapng']['combined_reply_hashes'],current_dropped_prefixes=dict(counts))))

if __name__=='__main__':main()
