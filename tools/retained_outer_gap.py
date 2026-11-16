"""Offline-only probe extension preserving last interval independently of maxima."""
from outer_loop_probe import OuterLoopProbe
class RetainingProbe(OuterLoopProbe):
    def __init__(self,*a,**k):super().__init__(*a,**k);self.last_gap=None
    def before_tick(self):
        self.last_gap=super().before_tick();return self.last_gap
    def summary(self):
        result=super().summary();result['last_gap']=self.last_gap;return result

def bind_to_fault(gap,fault):
    if gap is None or fault is None:return dict(matched=False,reason='missing interval or fault')
    context=fault.get('context',[])
    if len(context)<2 or fault.get('tick_entry') is None:return dict(matched=False,reason='missing clock context')
    previous=context[-2]['end'];entry=fault['tick_entry']
    valid=previous<=gap['start']<=gap['end']<=entry
    return dict(matched=valid,reason='interval inside final fault iteration' if valid else 'interval is not final fault iteration',previous_tick_end=previous,fault_tick_entry=entry)
