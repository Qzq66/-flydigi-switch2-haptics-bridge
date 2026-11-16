"""Bounded raw read-only HID evidence wrapper; no hardware opened on import."""
import ctypes as C,time,hashlib
class ReadOnlyTrace:
    def __init__(self,lib,clock=time.perf_counter,max_events=4096,max_bytes=1048576):
        self.lib=lib;self.clock=clock;self.max_events=max_events;self.max_bytes=max_bytes;self.events=[];self.raw_bytes=0
    def __getattr__(self,name):return getattr(self.lib,name)
    def reserve(self,n):
        if len(self.events)>=self.max_events or self.raw_bytes+n>self.max_bytes:raise ValueError('Read trace capacity exceeded')
    def hid_write(self,handle,buffer,size):
        self.reserve(size);raw=C.string_at(buffer,size)
        if len(raw)!=33 or raw[:3]!=bytes((0,0x5a,0xa5)) or raw[3] not in (4,0xa1,0xa3):raise ValueError('Trace permits identity/state/config reads only')
        if raw[3]==0xa3 and (raw[5] not in (0,1) or raw[6] not in (1,4,5,6)):raise ValueError('Non-read RAM payload rejected')
        start=self.clock();result=self.lib.hid_write(handle,buffer,size)
        self.events.append(dict(kind='query',start=start,end=self.clock(),raw_hex=raw.hex(),result=result));self.raw_bytes+=size;return result
    def hid_read_timeout(self,handle,buffer,size,timeout):
        self.reserve(size);start=self.clock();count=self.lib.hid_read_timeout(handle,buffer,size,timeout)
        raw=C.string_at(buffer,count) if count>0 else b''
        self.events.append(dict(kind='reply' if count>0 else 'read_wait',start=start,end=self.clock(),count=count,raw_hex=raw.hex()));self.raw_bytes+=len(raw);return count

def compare_bytes(before,after):
    return dict(identical=before==after,before_bytes=len(before),after_bytes=len(after),before_sha256=hashlib.sha256(before).hexdigest(),after_sha256=hashlib.sha256(after).hexdigest(),different_offsets=[i for i in range(max(len(before),len(after))) if (before[i] if i<len(before) else None)!=(after[i] if i<len(after) else None)])

def assess_reads(rows):
    if not rows:raise ValueError('No configuration samples')
    matches=[all(x['identical'] for x in r['comparisons'].values()) for r in rows]
    return dict(samples=len(rows),first_sample_matches=matches[0],all_samples_match=all(matches),mismatching_samples=[i for i,v in enumerate(matches) if not v],later_matches_do_not_override_first=True)
