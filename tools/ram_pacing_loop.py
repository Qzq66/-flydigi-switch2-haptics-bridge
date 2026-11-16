"""Bounded idle polling with phase observations; no device or file APIs."""
import math,time

class PhaseObserver:
    def __init__(self,limit=7500):
        self.limit=limit;self.rows=[];self.overflow=0;self.maximum_cost=0.
    def record(self,row,clock):
        begin=clock()
        if len(self.rows)>=self.limit:
            self.overflow+=1
            raise ValueError('Phase observation capacity exhausted')
        self.rows.append(row)
        end=clock()
        if not math.isfinite(end) or end<begin:raise ValueError('Observer clock reversed')
        self.maximum_cost=max(self.maximum_cost,end-begin)

def poll_window(client,observer,clock=time.perf_counter,pause=time.sleep,seconds=30.,maximum_queries=7500):
    started=clock();last=started;queries=accepted=0
    if not math.isfinite(started):raise ValueError('Invalid starting clock')
    def tick():
        nonlocal last
        now=clock()
        if not math.isfinite(now) or now<last:raise ValueError('Polling clock reversed')
        last=now;return now
    while True:
        now=tick()
        if now-started>=seconds:break
        if queries>=maximum_queries:raise ValueError('Polling query bound reached before deadline')
        if len(observer.rows)>=observer.limit:raise ValueError('Phase observation capacity exhausted')
        before=tick();frame=client.poll();after=tick();queries+=1
        if frame is not None:
            if frame['events'] or frame['flags']&24:raise ValueError('Unexpected upstream or early terminal phase')
            accepted+=1
        sleep_before=tick();pause(.004);sleep_after=tick()
        observer.record(dict(index=queries-1,poll_start=before,poll_end=after,
            sleep_start=sleep_before,sleep_end=sleep_after,accepted=frame is not None),clock)
    if not accepted:raise ValueError('No valid replies')
    return dict(completed_window=True,elapsed_seconds=now-started,poll_calls=queries,accepted_frames=accepted,
        deadline_expirations=client.deadline_expirations,late_matching_replies=client.late_matching_replies,
        stale_replies=client.stale_replies,phase_rows=len(observer.rows),phase_overflow=observer.overflow,
        maximum_phase_append_seconds=observer.maximum_cost)
