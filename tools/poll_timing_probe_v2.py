"""Independent critical/worst-gap retention; old hardware-run probe unchanged."""
import collections,copy
from poll_timing_probe import DetailedClient

class RetainedTimingClient(DetailedClient):
    def __init__(self,client,**kwargs):
        super().__init__(client,**kwargs)
        self.critical=collections.deque(maxlen=32);self.worst_gap=None

    def poll(self,*args,**kwargs):
        before=list(self.details)[-3:]
        try:return super().poll(*args,**kwargs)
        finally:
            item=self.details[-1];gap=item.get('response_gap')
            if item['outcome'] in ('error','timeout') or gap is not None and gap>.080:
                self.critical.append(copy.deepcopy(dict(before=before,event=item)))
            if gap is not None and (self.worst_gap is None or gap>self.worst_gap['event']['response_gap']):
                self.worst_gap=copy.deepcopy(dict(before=before,event=item))

    def snapshot(self):
        result=super().snapshot()
        result.update(critical_events=copy.deepcopy(list(self.critical)),worst_response_gap_context=copy.deepcopy(self.worst_gap))
        return result
