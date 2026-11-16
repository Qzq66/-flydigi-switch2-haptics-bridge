"""Bounded host-call timings; original transport remains owner of packet acceptance."""
import collections,copy,math,time
class PollBreakdown:
    POLLS=32768;CALLS=8;RECENT=64;SLOW=16
    def __init__(self,source,clock=time.perf_counter):
        self.source=source;self.clock=clock;self.current=None;self.polls=0;self.errors=0;self.failed=False
        self.recent=collections.deque(maxlen=self.RECENT);self.slow=[];self.maximum_gap=None;self.last_frame=None;self.max_observer=0.
    def begin(self):
        if self.failed or self.current is not None or self.polls>=self.POLLS:raise ValueError('Breakdown producer/budget fault')
        self.current=dict(poll_index=self.polls+1,start=self.clock(),calls=[])
    def invoke(self,kind,fn,*args):
        if self.failed or self.current is None or len(self.current['calls'])>=self.CALLS:
            self.failed=True;self.errors+=1;raise ValueError('Breakdown call budget exhausted')
        start=self.clock();error=None
        try:return fn(*args)
        except BaseException as e:error=type(e).__name__;raise
        finally:
            end=self.clock()
            if not math.isfinite(start) or not math.isfinite(end) or end<start:self.failed=True;self.errors+=1;raise ValueError('Breakdown call clock')
            self.current['calls'].append(dict(kind=kind,start=start,end=end,duration_seconds=end-start,error_type=error))
    def read_input(self):return self.invoke('input_read',self.source)
    def finish(self,frame=None,error=None):
        began=self.clock();row=self.current
        if error:self.failed=True;self.errors+=1
        if row is None:raise ValueError('No breakdown poll')
        row.update(end=began,duration_seconds=began-row['start'],outcome='error' if error else ('frame' if frame is not None else 'timeout'),error_type=error)
        if row['duration_seconds']<0 or not math.isfinite(row['duration_seconds']):self.failed=True;self.errors+=1;raise ValueError('Breakdown poll clock')
        gap=0.
        if frame is not None:
            at=frame['received_at']
            if not row['start']<=at<=began:self.failed=True;self.errors+=1;raise ValueError('Breakdown accepted time')
            gap=0. if self.last_frame is None else at-self.last_frame['received_at']
            row.update(received_at=at,receive_gap_seconds=gap,source_us=frame['source_us'],flags=frame['flags'])
            if self.last_frame is not None and (self.maximum_gap is None or gap>self.maximum_gap['row']['receive_gap_seconds']):self.maximum_gap=dict(row=row,previous_frame=self.last_frame)
            self.last_frame=row
        row['score_seconds']=max(gap,row['duration_seconds']);self.recent.append(row)
        if len(self.slow)<self.SLOW:self.slow.append(row)
        else:
            weakest=min(self.slow,key=lambda r:r['score_seconds'])
            if row['score_seconds']>weakest['score_seconds']:self.slow.remove(weakest);self.slow.append(row)
        self.polls+=1;self.current=None;self.max_observer=max(self.max_observer,self.clock()-began)
    def snapshot(self):
        # Final snapshot only, after producer join; no live concurrent reader.
        return copy.deepcopy(dict(version=1,healthy=not self.failed and not self.errors,errors=self.errors,poll_calls=self.polls,
            in_flight=self.current,recent=list(self.recent),slowest=list(self.slow),maximum_receive_gap=self.maximum_gap,
            limits=dict(polls=self.POLLS,calls_per_poll=self.CALLS,recent=self.RECENT,slow=self.SLOW),maximum_finish_observer_seconds=self.max_observer,
            packet_or_peer_or_session_recorded=False,scope='Host API calls include scheduling; recvfrom timing is not pure radio latency. Reply validity remains original Client responsibility.'))
class TimedSocket:
    def __init__(self,sock,probe):self.sock=sock;self.probe=probe
    def __getattr__(self,name):return getattr(self.sock,name)
    def sendto(self,*args):return self.probe.invoke('sendto',self.sock.sendto,*args)
    def recvfrom(self,*args):return self.probe.invoke('recvfrom',self.sock.recvfrom,*args)
class BreakdownClient:
    def __init__(self,client,probe):self.client=client;self.probe=probe;client.sock=TimedSocket(client.sock,probe)
    def __getattr__(self,name):return getattr(self.client,name)
    def poll(self,*a,**k):
        self.probe.begin()
        try:frame=self.client.poll(*a,**k)
        except BaseException as e:self.probe.finish(error=type(e).__name__);raise
        self.probe.finish(frame=frame);return frame
    def confirm_end(self):
        # Original Client policy: at most three calls, same final_ack argument.
        for _ in range(3):
            frame=self.poll(final_ack=True)
            if frame is not None:return frame
        return None
