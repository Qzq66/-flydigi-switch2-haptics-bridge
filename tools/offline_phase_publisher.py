"""Bounded prototype only. Injected UI writer; no device/network or live entry hook."""
import json,threading
PHASES=frozenset(('DISCOVERING','WAITING_SOURCE','INPUT_READY','ARMED','MUTED','MUTED_FAULT','ENDED'))
class PhasePublisher:
    def __init__(self,writer):
        self.writer=writer;self.cv=threading.Condition();self.pending=None;self.closed=False;self.error=None
        self.posted=0;self.written=0;self.coalesced=0
        self.thread=threading.Thread(target=self._run,daemon=True);self.thread.start()
    def publish(self,phase,**fields):
        if phase not in PHASES or len(fields)>16:raise ValueError('Invalid phase payload')
        if any(type(v) not in (str,int,float,bool,type(None)) for v in fields.values()):raise ValueError('Primitive phase fields only')
        data=dict(fields,phase=phase,clock='monotonic');payload=json.dumps(data,allow_nan=False)
        if len(payload.encode('utf-8'))>2048:raise ValueError('Phase payload cap')
        with self.cv:
            self._check_locked()
            if self.closed:raise RuntimeError('Publisher closed')
            if self.pending is not None:self.coalesced+=1
            self.pending=payload;self.posted+=1;self.cv.notify()
    def _check_locked(self):
        if self.error is not None:raise RuntimeError('Phase writer failed: '+self.error)
    def check(self):
        with self.cv:self._check_locked()
    def _run(self):
        while True:
            with self.cv:
                while self.pending is None and not self.closed:self.cv.wait()
                if self.pending is None and self.closed:return
                payload=self.pending;self.pending=None
            try:self.writer(payload)
            except BaseException as exc:
                with self.cv:self.error=repr(exc)
                return
            with self.cv:self.written+=1
    def close(self,timeout=1.):
        if not 0<=timeout<=5:raise ValueError('Bounded close timeout required')
        with self.cv:self.closed=True;self.cv.notify()
        self.thread.join(timeout)
        if self.thread.is_alive():raise TimeoutError('Phase writer did not finish; never force-killed')
        self.check()
    def summary(self):
        with self.cv:return dict(posted=self.posted,written=self.written,coalesced=self.coalesced,pending_count=int(self.pending is not None),error=self.error,closed=self.closed)
