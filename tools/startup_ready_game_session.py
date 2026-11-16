"""Independent startup gate; no device access or changes to active output policy."""
import math,time
from multi_event_game_session import MultiGameSession
from live_fidelity_candidate import BridgeFault

class StartupReadyGameSession(MultiGameSession):
    def __init__(self,enable,send,stop,clock=time.perf_counter,pause=time.sleep):
        super().__init__(enable,send,stop,clock,pause)
        self.startup_quiet_since=None
        self.startup_stale=False
        self.startup_gap_count=0

    def invalidate_startup(self):
        if not self.startup_stale:self.startup_gap_count+=1
        self.startup_stale=True
        self.startup_quiet_since=None

    def feed(self,frame):
        r=self.output.renderer
        if not r.armed:
            if r.last_received is not None and frame['received_at']-r.last_received>.080:
                self.invalidate_startup()
        super().feed(frame)
        if r.armed or self.output.fault or self.terminal:return
        values=[d.output() for d in r.decoders]
        configured=frame['flags']&6==6 and not frame['flags']&8
        neutral=all(v['state_complete'] and not(v['low_amplitude'] or v['high_amplitude']) for v in values)
        if not configured or not neutral:
            self.startup_quiet_since=None
        elif self.startup_quiet_since is None:
            # A recovered packet starts a new quiet qualification, never arms.
            self.startup_quiet_since=frame['received_at']
        self.startup_stale=False

    def tick(self):
        r=self.output.renderer
        if self.output.fault or self.terminal:return
        if r.armed:return super().tick()
        now=self.clock()
        if not math.isfinite(now):self.fail('Invalid startup clock');return
        if r.last_received is None or now-r.last_received>.080:
            self.invalidate_startup()
        elif now<r.last_received:self.fail('Startup clock reversed')
        # No PCM render/enable/send call before explicit arm.

    def source_ready(self):
        now=self.clock()
        return (self.startup_quiet_since is not None
            and not self.startup_stale
            and now-self.startup_quiet_since>=.5
            and super().source_ready())

    def arm(self,controls_neutral,live_elapsed):
        if not self.source_ready():
            self.arm_attempted=True
            self.fail('Startup source not qualified for manual arm')
            raise BridgeFault('Startup source not qualified for manual arm')
        return super().arm(controls_neutral,live_elapsed)

    def summary(self):
        result=super().summary()
        result['startup_gate']=dict(version=1,quiet_seconds=.5,heartbeat_seconds=.080,
            stale_intervals=self.startup_gap_count,automatic_arm=False,
            active_policy_unchanged=True)
        return result
