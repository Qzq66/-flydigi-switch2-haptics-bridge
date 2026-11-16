"""Offline wait-policy candidate only; does not alter any renderer protection."""
import math
BASE_WAIT=.001
GUARD=.003

def request(now,target,active):
    if not math.isfinite(now):raise ValueError('Nonfinite host clock')
    if not active or target is None:return BASE_WAIT
    if not math.isfinite(target):raise ValueError('Nonfinite target')
    return min(BASE_WAIT,max(0.,target-now-GUARD))

class WaitProxy:
    def __init__(self,base,current_game):self.base=base;self.current_game=current_game;self.calls=0;self.skipped=0
    def __getattr__(self,name):return getattr(self.base,name)
    def sleep(self,seconds):
        if seconds!=BASE_WAIT:return self.base.sleep(seconds)
        game=self.current_game();active=game is not None and game.output.renderer.armed and game.output.dirty and not game.output.fault
        duration=request(self.base.perf_counter(),game.target if game is not None else None,active)
        self.calls+=1
        if duration==0:self.skipped+=1;return None
        return self.base.sleep(duration)
