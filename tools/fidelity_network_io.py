"""Independent bounded USB injector and snapshot/reset handshake; injected I/O."""
import math,threading,time
from live_fidelity_candidate import BridgeFault

SNAPSHOT=b'SNAP043\1'

class CapturedInjector:
    """Only this worker owns Pico USB writes while PCM dispatch is active.

    Cancellation cannot interrupt a native HID write already in progress. The
    caller must stop output immediately, then require join before any USB read
    or reset. A stuck worker fails the run and is left to the process guardian.
    """
    def __init__(self,events,start,send,maximum_lateness=.004,clock=time.perf_counter,wait=None):
        self.events=tuple(dict(e) for e in events);self.start_at=start;self.send=send;self.limit=maximum_lateness;self.clock=clock
        self.stop_event=threading.Event();self.done=threading.Event();self.wait=wait or self.stop_event.wait
        self.thread=None;self.error=None;self.cancelled=False;self.writes=[];self.used=False
        if not math.isfinite(start) or maximum_lateness!=.004 or not 0<len(self.events)<=256:raise ValueError('Unsupported injection bounds')
        previous=-1
        for e in self.events:
            if type(e['at_us']) is not int or not 0<=e['at_us']<=320000 or e['at_us']<=previous or len(bytes.fromhex(e['motors']))!=8:raise ValueError('Invalid ordered captured event')
            previous=e['at_us']

    def run(self):
        if self.used:raise RuntimeError('USB injection is one-shot')
        self.used=True
        try:
            for index,e in enumerate(self.events):
                due=self.start_at+e['at_us']/1e6
                while self.clock()<due and not self.stop_event.is_set():self.wait(min(.001,due-self.clock()))
                if self.stop_event.is_set():self.cancelled=True;break
                started=self.clock();late=started-due
                if not math.isfinite(late) or not 0<=late<=self.limit:raise BridgeFault('USB injection late; no catch-up')
                self.send(index,bytes.fromhex(e['motors']))
                ended=self.clock();duration=ended-started
                self.writes.append(dict(motors=e['motors'],started_at=started,finished_at=ended,lateness_seconds=late,write_seconds=duration))
                if not math.isfinite(duration) or not 0<=duration<=.080:raise BridgeFault('USB write exceeded bounded native call duration')
        except BaseException as exc:self.error=repr(exc)
        finally:self.done.set()

    def start(self):
        if self.thread is not None or self.used:raise RuntimeError('USB injection is one-shot')
        self.thread=threading.Thread(target=self.run,name='captured-pico-usb-injector',daemon=True);self.thread.start()

    def join(self,timeout=1):
        if self.thread:self.thread.join(timeout)
        return self.done.is_set() and (self.thread is None or not self.thread.is_alive())

    def cancel_and_join(self,timeout=1):
        self.stop_event.set();return self.join(timeout)

    def evidence(self):
        writes=tuple(self.writes)
        return dict(injector_done=self.done.is_set(),injector_error=self.error,injector_cancelled=self.cancelled,
            sent_motor_fields=[w['motors'] for w in writes],injection_lateness_seconds=[w['lateness_seconds'] for w in writes],
            injection_write_seconds=[w['write_seconds'] for w in writes])

def snapshot_then_reset(read_marker,send_reset,clock=time.monotonic,pause=time.sleep,timeout=8):
    """Never send RESETLAB during the ending-but-not-snapshot interval."""
    until=clock()+timeout;attempts=0
    while True:
        attempts+=1
        try:marker=read_marker()
        except (TimeoutError,OSError,AssertionError):marker=None
        if marker==SNAPSHOT:
            send_reset();return dict(snapshot_phase_confirmed=True,snapshot_probe_attempts=attempts,pico_ram_reset_requested=True)
        if clock()>=until:raise TimeoutError('Exact RAM snapshot phase not confirmed; reset not sent')
        pause(.05)

def wait_full_flash(verify,timeout=30,clock=time.monotonic,pause=time.sleep):
    """Poll the real full-Flash comparison while Windows enumerates BOOTSEL.

    Never search for RAM or request another reset after just one transient miss.
    Verification errors propagate; elapsed time or missing devices cannot pass.
    """
    start=clock();attempts=0
    while True:
        attempts+=1;matched=verify();elapsed=clock()-start
        if not math.isfinite(elapsed) or elapsed<0:raise ValueError('Invalid BOOTSEL wait clock')
        if matched is True:return dict(matched=True,attempts=attempts,elapsed_seconds=elapsed)
        if elapsed>=timeout:return dict(matched=False,attempts=attempts,elapsed_seconds=elapsed)
        pause(min(.25,timeout-elapsed))
