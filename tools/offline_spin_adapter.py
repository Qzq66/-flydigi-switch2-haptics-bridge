"""Reuse the existing 2ms spin helper with isolated globals; host replay only."""
import types

class SpinTime:
    def __init__(self,base,game,source=None):
        if source is None:
            import sustained_game_spin_child as source
        if source.SPIN_MARGIN!=.002:raise ValueError('Existing experimental margin changed')
        self.base=base;self.game=game
        self.state=dict(enabled=False,spins=0,spin_seconds=0.,maximum_spin_seconds=0.)
        # Use the same function code, without mutating the caller process env,
        # module clock, or shared counters. No child/plan/backend is invoked.
        scope=dict(source.wait.__globals__)
        scope.update(os=types.SimpleNamespace(environ={'FLYDIGI_SPIN_WAIT':'1'}),
            time=base,_stats=self.state)
        self.wait=types.FunctionType(source.wait.__code__,scope,'offline_existing_spin_wait')
    def __getattr__(self,name):return getattr(self.base,name)
    def sleep(self,seconds):
        if seconds!=.001:return self.base.sleep(seconds)
        return self.wait(self.game())
    def summary(self):return dict(self.state,margin_seconds=.002,process_environment_modified=False)
