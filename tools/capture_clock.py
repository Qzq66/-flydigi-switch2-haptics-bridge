"""Local UTC/per-process performance-clock anchors; native API loaded on demand."""
import math,time
FILETIME_UNIX_EPOCH=116444736000000000

def precise_utc_reader():
    import ctypes,sys
    if sys.platform!='win32':raise RuntimeError('Windows precise UTC required')
    api=ctypes.WinDLL('kernel32',use_last_error=True).GetSystemTimePreciseAsFileTime
    api.argtypes=[ctypes.POINTER(ctypes.c_ulonglong)];api.restype=None
    def read():
        value=ctypes.c_ulonglong();api(ctypes.byref(value))
        return (value.value-FILETIME_UNIX_EPOCH)*100
    return read

def anchor(utc,clock=time.perf_counter,samples=5):
    values=[]
    for _ in range(samples):
        before=clock();ns=utc();after=clock()
        if not all(math.isfinite(v) for v in (before,after)) or after<before or not isinstance(ns,int):raise ValueError('Invalid clock sample')
        values.append(dict(perf_mid=(before+after)/2,utc_ns=ns,bracket_ns=round((after-before)*1e9)))
    return min(values,key=lambda v:v['bracket_ns'])

def map_to_utc(perf,anchors):
    a,b=anchors[0],anchors[-1];span=b['perf_mid']-a['perf_mid']
    if span<=0 or b['utc_ns']<=a['utc_ns']:raise ValueError('Clock ordering')
    drift=(b['utc_ns']-a['utc_ns'])-span*1e9
    if abs(drift)>2_000_000 or max(a['bracket_ns'],b['bracket_ns'])>1_000_000:raise ValueError('Clock mapping uncertainty too large')
    if not a['perf_mid']-.01<=perf<=b['perf_mid']+.01:raise ValueError('Outside anchor interval')
    return round(a['utc_ns']+(perf-a['perf_mid'])/span*(b['utc_ns']-a['utc_ns']))
