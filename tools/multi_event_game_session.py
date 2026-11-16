"""Game source/archive/quiet gate reused with independent bounded multi output."""
import time
from fidelity_game_policy import GameSession
from bounded_multi_event_session import MultiEventSession
class MultiGameSession(GameSession):
    def __init__(self,enable,send,stop,clock=time.perf_counter,pause=time.sleep):
        super().__init__(enable,send,stop,clock,pause)
        self.output=MultiEventSession(enable,send,stop,clock,pause)
