"""Bounded timing observation; never retries, changes packets or owns output."""
import collections,time

class ObservedClient:
    def __init__(self,client,clock=time.perf_counter):
        self.client=client;self.clock=clock;self.calls=0;self.responses=0;self.timeouts=0
        self.max_call=0.;self.max_gap=0.;self.last_received=None
        self.boots=[];self.recent=collections.deque(maxlen=64);self.first=None

    def __getattr__(self,name):return getattr(self.client,name)

    def poll(self,*args,**kwargs):
        start=self.clock();self.calls+=1
        try:frame=self.client.poll(*args,**kwargs)
        except BaseException as exc:
            self.recent.append(dict(kind='error',at=self.clock(),error=repr(exc)))
            raise
        end=self.clock();self.max_call=max(self.max_call,end-start)
        if frame is None:
            self.timeouts+=1;self.recent.append(dict(kind='timeout',at=end,duration=end-start))
        else:
            now=frame['received_at'];gap=None if self.last_received is None else now-self.last_received
            if gap is not None:self.max_gap=max(self.max_gap,gap)
            self.last_received=now;self.responses+=1
            if frame['boot'] not in self.boots and len(self.boots)<4:self.boots.append(frame['boot'])
            item=dict(kind='frame',at=now,duration=end-start,gap=gap,source_us=frame['source_us'],
                flags=frame['flags'],events=len(frame['events']),rtt_ms=frame.get('rtt_ms'))
            if self.first is None:self.first=dict(item)
            self.recent.append(item)
        return frame

    def confirm_end(self):
        # Match the accepted Client contract, but observe each bounded attempt.
        for _ in range(3):
            frame=self.poll(final_ack=True)
            if frame is not None:return frame
        return None

    def snapshot(self):
        return dict(poll_calls=self.calls,responses=self.responses,timeouts=self.timeouts,
            maximum_poll_call_seconds=self.max_call,maximum_response_gap_seconds=self.max_gap,
            observed_boot_ids=list(self.boots),first_frame=self.first,recent=list(self.recent))

