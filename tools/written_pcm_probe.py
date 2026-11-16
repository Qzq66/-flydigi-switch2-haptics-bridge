"""Bounded summaries after a validated waveform writer returns successfully.

No I/O except the injected writer. A successful API return is not a device ACK.
Never stores PCM arrays or retries a write; errors latch and propagate to caller.
"""
import hashlib,math,time
MAX_FRAMES=1900

def encode_report(left,right):
    if len(left)!=8 or len(right)!=8:raise ValueError('Eight samples per channel required')
    if any(type(v) is not int or abs(v-128)>12 for v in list(left)+list(right)):raise ValueError('Invalid sample')
    frame=bytearray(33);frame[1:6]=bytes((0x5a,0xa5,0x57,0x1b,0x98))
    for i,(l,r) in enumerate(zip(left,right)):frame[6+3*i:9+3*i]=bytes((128,l,r))
    frame[32]=sum(frame[3:32])&255
    return bytes(frame)

def parse_report(report):
    if type(report) is not bytes or len(report)!=33 or report[:6]!=bytes((0,0x5a,0xa5,0x57,0x1b,0x98)):raise ValueError('Unexpected waveform report')
    if report[30:32]!=bytes(2) or report[32]!=sum(report[3:32])&255:raise ValueError('Invalid report padding or checksum')
    if any(report[6+3*i]!=128 for i in range(8)):raise ValueError('Unexpected third channel')
    left=bytes(report[7+3*i] for i in range(8));right=bytes(report[8+3*i] for i in range(8))
    if any(abs(v-128)>12 for v in left+right):raise ValueError('Report sample bound')
    return left,right

class WrittenPCMProbe:
    def __init__(self,writer,frame_limit=MAX_FRAMES,clock=time.perf_counter):
        if type(frame_limit) is not int or not 1<=frame_limit<=MAX_FRAMES:raise ValueError('Invalid bounded observer capacity')
        self.writer=writer;self.limit=frame_limit;self.clock=clock;self.last_clock=None
        self.attempts=self.writer_successes=self.recorded_frames=self.write_failures=self.record_errors=self.rejected=0
        self.faulted=False;self.uncertain_write=False;self.maximum_cost=self.maximum_write=0.
        self._left=hashlib.sha256();self._right=hashlib.sha256();self._wire=hashlib.sha256()
        self.dose=[0,0];self.peak=[0,0];self.nonneutral=[0,0]
    def _time(self):
        now=self.clock()
        if not math.isfinite(now) or self.last_clock is not None and now<self.last_clock:raise ValueError('Observer clock invalid')
        self.last_clock=now;return now
    def send(self,report):
        if self.faulted:raise RuntimeError('PCM observation fault latched')
        try:
            begin=self._time()
            if self.recorded_frames>=self.limit:raise ValueError('PCM observation capacity')
            left,right=parse_report(report)
            dose=[sum((v-128)**2 for v in side) for side in (left,right)]
            if any(a+b>8000 for a,b in zip(self.dose,dose)):raise ValueError('PCM code energy bound')
            write_start=self._time()
        except BaseException:
            self.rejected+=1;self.faulted=True;raise
        self.attempts+=1
        try:
            outcome=self.writer(report)
            if outcome is not None:raise RuntimeError('Validated writer return contract changed')
        except BaseException:
            self.write_failures+=1;self.uncertain_write=True;self.faulted=True;raise
        self.writer_successes+=1
        try:
            write_end=self._time()
            # Commit copied hash state only when every update succeeds.
            lh,rh,wh=self._left.copy(),self._right.copy(),self._wire.copy()
            lh.update(left);rh.update(right);wh.update(report)
            peaks=[max(abs(v-128) for v in side) for side in (left,right)]
            nonneutral=[sum(v!=128 for v in side) for side in (left,right)]
            self._left,self._right,self._wire=lh,rh,wh
            self.dose=[a+b for a,b in zip(self.dose,dose)]
            self.peak=[max(a,b) for a,b in zip(self.peak,peaks)]
            self.nonneutral=[a+b for a,b in zip(self.nonneutral,nonneutral)]
            self.recorded_frames+=1
            end=self._time();self.maximum_write=max(self.maximum_write,write_end-write_start)
            self.maximum_cost=max(self.maximum_cost,(write_start-begin)+(end-write_end))
        except BaseException:
            self.record_errors+=1;self.faulted=True;raise
    def snapshot(self):
        result=dict(version=1,observation_point='after_validated_writer_successful_return',device_per_frame_ack=False,
            frame_limit=self.limit,attempts=self.attempts,writer_successes=self.writer_successes,recorded_frames=self.recorded_frames,
            samples_per_side=self.recorded_frames*8,write_failures=self.write_failures,record_errors=self.record_errors,
            rejected_before_write=self.rejected,fault_latched=self.faulted,possible_partial_or_unconfirmed_write=self.uncertain_write,
            peak_per_side=list(self.peak),squared_code_sum=list(self.dose),nonneutral_samples=list(self.nonneutral),
            maximum_observer_seconds=self.maximum_cost,maximum_writer_call_seconds=self.maximum_write)
        try:result.update(left_sha256=self._left.hexdigest(),right_sha256=self._right.hexdigest(),report_sha256=self._wire.hexdigest())
        except BaseException:result['snapshot_error']=True
        result['complete']=not self.faulted and not result.get('snapshot_error') and self.writer_successes==self.recorded_frames and self.attempts==self.recorded_frames
        return result
