"""Bounded idle-Pico polling, with no input forwarding or actuator path."""
import math,time

def poll_window(client,clock=time.perf_counter,pause=time.sleep,seconds=30.,maximum_queries=7500):
    started=clock();last=started;queries=accepted=0
    while True:
        now=clock()
        if not math.isfinite(now) or now<last:raise ValueError('Polling clock reversed')
        last=now
        if now-started>=seconds:break
        if queries>=maximum_queries:raise ValueError('Polling query bound reached before deadline')
        frame=client.poll();queries+=1
        if frame is not None:
            if frame['events'] or frame['flags']&24:raise ValueError('Unexpected upstream or early terminal phase')
            accepted+=1
        pause(.004)
    if not accepted:raise ValueError('No valid replies')
    return dict(completed_window=True,elapsed_seconds=now-started,poll_calls=queries,accepted_frames=accepted,
        deadline_expirations=client.deadline_expirations,late_matching_replies=client.late_matching_replies,stale_replies=client.stale_replies)
