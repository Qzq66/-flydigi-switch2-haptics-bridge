"""Windows adapters; importing does not load DLLs or open devices."""
import sys,time,importlib.util,pathlib
from bridge_input import convert,NEUTRAL

def require_windows():
    if sys.platform!='win32':raise RuntimeError('Windows hardware backend unavailable')

def load_owner():
    require_windows()
    path=pathlib.Path(__file__).resolve().with_name('flydigi-owner-hotplug.py')
    spec=importlib.util.spec_from_file_location('owner',path)
    obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj)
    return obj

class TimerResolution:
    def __init__(self,library=None):self.library=library;self.active=False
    def start(self):
        if self.active:return True
        if self.library is None:
            require_windows()
            import ctypes
            self.library=ctypes.WinDLL('winmm')
        self.active=self.library.timeBeginPeriod(1)==0
        return self.active
    def close(self):
        if self.active:
            self.active=False
            self.library.timeEndPeriod(1)

class XInputSource:
    def __init__(self,xi=None):
        if xi is None:
            require_windows()
            import xinput_readonly as xi
        from bridge_protocol import BridgeFault
        self.xi=xi;self.fault=BridgeFault;slots=xi.connected()
        if len(slots)!=1:raise BridgeFault('Exactly one PC XInput controller required')
        self.slot=slots[0]
        self.changes=[];self.previous=None;self.nonneutral_reads=0
    def __call__(self):
        state=self.xi.read(self.slot)
        if state is None:raise self.fault('XInput source disconnected; relay stopped')
        value=convert(state.gamepad)
        self.last_read_at=time.perf_counter()
        if value!=NEUTRAL:
            self.nonneutral_reads+=1
            self.last_nonneutral_at=self.last_read_at
        if value!=self.previous:
            if len(self.changes)<64:self.changes.append(dict(at=time.perf_counter(),pro_input=value.hex()))
            self.previous=value
        return value
