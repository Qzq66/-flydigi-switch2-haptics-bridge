"""Offline-only integration candidate. No devices, network, or hardware CLI.

Input order and existing GameSession.tick remain unchanged. Phase-file writer is
injected and moved to one worker; timing observations stay bounded in memory.
"""
import collections,math,time
from offline_phase_publisher import PhasePublisher

class TickClock:
    def __init__(self,base):self.base=base;self.inside_tick=False;self.entry=None
    def __call__(self):
        value=self.base()
        if self.inside_tick and self.entry is None:self.entry=value
        return value

class CandidateLoop:
    def __init__(self,game,writer,clock=None):
        if game.output.renderer.armed or game.output.dirty:raise ValueError('Attach before manual arm')
        self.clock=TickClock(clock or game.clock);self.game=game
        self.game.clock=self.clock;self.game.output.clock=self.clock
        self.publisher=PhasePublisher(writer);self.recent=collections.deque(maxlen=32)
        self.first_fault=None;self.closed=False;self.steps=0;self.maximum_drain=0.;self.maximum_enqueue=0.
    def step(self,frames=(),phase=None,fields=None):
        if self.closed:raise RuntimeError('Candidate loop closed')
        self.clock.entry=None
        g=self.game;start=self.clock();target=None;before=g.output.frames;prior_fault=g.output.fault
        drain_end=enqueue_end=start;error=None
        try:
            self.publisher.check()
            # Preserve source ordering and full ingestion; never render ahead of
            # queued source updates solely to make a deadline statistic pass.
            for frame in frames:
                if isinstance(frame,BaseException):raise frame
                packet=dict(frame,processed_at=self.clock());g.feed(packet)
            drain_end=self.clock()
            if phase is not None:self.publisher.publish(phase,**(fields or {}))
            enqueue_end=self.clock();self.publisher.check()
            target=g.target;self.clock.entry=None;self.clock.inside_tick=True
            g.tick()
        except BaseException as exc:
            error=type(exc).__name__
            try:g.fail('Candidate loop error: '+type(exc).__name__)
            finally:raise
        finally:
            self.clock.inside_tick=False;end=self.clock();self.steps+=1
            row=dict(step=self.steps,start=start,drain_end=drain_end,enqueue_end=enqueue_end,
                tick_entry=self.clock.entry,target=target,end=end,
                frames_before=before,frames_after=g.output.frames,error=error)
            self.recent.append(row);self.maximum_drain=max(self.maximum_drain,drain_end-start)
            self.maximum_enqueue=max(self.maximum_enqueue,enqueue_end-drain_end)
            if g.output.fault and not prior_fault and self.first_fault is None:
                entry=self.clock.entry
                self.first_fault=dict(fault=g.output.fault,tick_entry=entry,target=target,
                    lateness_seconds=entry-target if entry is not None and target is not None else None,
                    frames_before=before,frames_after=g.output.frames,stop_confirmed=g.output.summary()['output_stop_confirmed'],
                    context=[dict(r) for r in self.recent],observed_before_stop_clock_value=entry is not None)
    def summary(self):
        return dict(steps=self.steps,maximum_drain_seconds=self.maximum_drain,maximum_enqueue_seconds=self.maximum_enqueue,
            recent=list(self.recent),first_fault=self.first_fault,publisher=self.publisher.summary(),
            integration_scope='offline injected backends only; not a hardware accepted runner')
    def close(self):
        # UI failure cannot prevent output stop. No forced worker termination.
        self.closed=True
        try:self.game.output.stop()
        finally:self.publisher.close()
