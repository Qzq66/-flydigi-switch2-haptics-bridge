"""Explicit software-timer candidate. Native library is loaded only on construction.
No device/network actions and no fallback or protection-parameter changes.
"""
import math
class WindowsTimerAPI:
    def __init__(self):
        import ctypes as C
        self.C=C;self.lib=C.WinDLL('kernel32',use_last_error=True)
        self.lib.CreateWaitableTimerExW.argtypes=[C.c_void_p,C.c_wchar_p,C.c_ulong,C.c_ulong];self.lib.CreateWaitableTimerExW.restype=C.c_void_p
        self.lib.SetWaitableTimerEx.argtypes=[C.c_void_p,C.POINTER(C.c_longlong),C.c_long,C.c_void_p,C.c_void_p,C.c_void_p,C.c_ulong];self.lib.SetWaitableTimerEx.restype=C.c_int
        self.lib.WaitForSingleObject.argtypes=[C.c_void_p,C.c_ulong];self.lib.WaitForSingleObject.restype=C.c_ulong
        self.lib.CancelWaitableTimer.argtypes=[C.c_void_p];self.lib.CancelWaitableTimer.restype=C.c_int
        self.lib.CloseHandle.argtypes=[C.c_void_p];self.lib.CloseHandle.restype=C.c_int
    def create(self):return self.lib.CreateWaitableTimerExW(None,None,2,0x1f0003)
    def arm(self,h,ticks):
        due=self.C.c_longlong(ticks);return self.lib.SetWaitableTimerEx(h,self.C.byref(due),0,None,None,None,0)
    def wait(self,h,timeout_ms):return self.lib.WaitForSingleObject(h,timeout_ms)
    def cancel(self,h):return self.lib.CancelWaitableTimer(h)
    def close(self,h):return self.lib.CloseHandle(h)

class HighResolutionWait:
    def __init__(self,api=None):
        self.api=api if api is not None else WindowsTimerAPI();self.handle=self.api.create()
        if not self.handle:raise OSError('High-resolution timer unavailable; no fallback')
    def sleep(self,seconds):
        if self.handle is None:raise RuntimeError('Timer closed')
        if not math.isfinite(seconds) or not 0<seconds<=.001:raise ValueError('Only positive waits up to existing1ms are allowed')
        if not self.api.arm(self.handle,-max(1,math.ceil(seconds*10000000))):raise OSError('Timer arm failed')
        status=self.api.wait(self.handle,4)
        if status!=0:
            self.api.cancel(self.handle)
            if status==258:raise TimeoutError('Software timer wait timed out')
            raise OSError('Software timer wait failed')
    def close(self):
        if self.handle is None:return
        handle=self.handle;self.api.cancel(handle)
        if not self.api.close(handle):raise OSError('Timer close failed')
        self.handle=None

def blocking_request(now,target,active):
    if not math.isfinite(now):raise ValueError('Nonfinite clock')
    if not active or target is None:return .001
    if not math.isfinite(target):raise ValueError('Nonfinite target')
    return min(.001,max(0.,target-now))
