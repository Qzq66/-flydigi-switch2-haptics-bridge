"""Startup-qualified60second session; independent output adapter."""
import time
from startup_ready_game_session import StartupReadyGameSession
from sustained_session import SustainedSession
class SustainedGameSession(StartupReadyGameSession):
    def __init__(self,enable,send,stop,clock=time.perf_counter,pause=time.sleep):
        super().__init__(enable,send,stop,clock,pause)
        self.output=SustainedSession(enable,send,stop,clock,pause)
    def summary(self):
        result=super().summary()
        result['startup_gate'].update(active_policy_unchanged=False,active_timing_protection_unchanged=True,budget_variant='60s6events')
        return result
