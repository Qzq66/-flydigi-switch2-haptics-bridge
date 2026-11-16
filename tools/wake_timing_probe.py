"""Measure existing collector sleeps without changing duration or creating threads."""
import collections,copy,math,time
from poll_timing_probe_v2 import RetainedTimingClient

class SleepProbe:
    def __init__(self,clock=time.perf_counter,pause=time.sleep):
        self.clock=clock;self.pause=pause;self.count=0;self.requested_total=0.;self.actual_total=0.
        self.last=None;self.worst=None;self.recent=collections.deque(maxlen=64);self.large=collections.deque(maxlen=32)
        self.buckets=[0,0,0,0,0]

    def __call__(self,seconds):
        if not math.isfinite(seconds) or seconds<0:raise ValueError('Invalid sleep duration')
        start=self.clock();self.pause(seconds);end=self.clock();actual=end-start
        if not math.isfinite(actual) or actual<0:raise ValueError('Sleep clock reversed')
        sample=dict(start=start,end=end,requested_seconds=seconds,actual_seconds=actual,overshoot_seconds=max(0.,actual-seconds))
        self.count+=1;self.requested_total+=seconds;self.actual_total+=actual
        self.last=sample;self.recent.append(sample)
        if self.worst is None or sample['overshoot_seconds']>self.worst['overshoot_seconds']:self.worst=dict(sample)
        if sample['overshoot_seconds']>.008:self.large.append(sample)
        index=next((i for i,bound in enumerate((.001,.004,.010,.020)) if sample['overshoot_seconds']<=bound),4)
        self.buckets[index]+=1

    def snapshot(self):
        return dict(count=self.count,requested_total_seconds=self.requested_total,actual_total_seconds=self.actual_total,
            mean_actual_seconds=self.actual_total/self.count if self.count else None,
            worst=copy.deepcopy(self.worst),recent=copy.deepcopy(list(self.recent)),large_overshoots=copy.deepcopy(list(self.large)),
            overshoot_bucket_upper_ms=[1,4,10,20,None],overshoot_bucket_counts=list(self.buckets),
            scope='Existing sleep calls only; overshoot includes scheduler and execution overhead, not a proved cause.')

class WakeObservedClient(RetainedTimingClient):
    def __init__(self,client,sleep_probe,**kwargs):
        super().__init__(client,**kwargs);self.sleep_probe=sleep_probe

    def poll(self,*args,**kwargs):
        before=copy.deepcopy(self.sleep_probe.last)
        if before is not None and (self.last_end is None or before['start']<self.last_end):before=None
        try:return super().poll(*args,**kwargs)
        finally:
            item=self.details[-1];item['collector_sleep_before_poll']=before
            contexts=list(self.critical)
            if self.worst_gap is not None:contexts.append(self.worst_gap)
            for context in contexts:
                if context['event']['start']==item['start']:
                    context['event']['collector_sleep_before_poll']=copy.deepcopy(before)

    def snapshot(self):
        result=super().snapshot();result['collector_sleep']=self.sleep_probe.snapshot();return result
