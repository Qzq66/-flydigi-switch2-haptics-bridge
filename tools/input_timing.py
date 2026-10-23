"""Pure countdown policy, anchored to the actual child INPUT_READY clock."""
import math

def view(data,now):
    if data.get('phase')=='ENDED':return 'ENDED',0
    start=data.get('started_at_monotonic')
    if data.get('clock')!='monotonic' or data.get('phase')!='INPUT_READY' or type(start) not in (int,float) or not math.isfinite(start) or start<=0:return 'WAITING',0
    elapsed=now-start
    if elapsed<0:return 'WAITING',0
    if elapsed>=120:return 'ENDED',0
    if elapsed<30:return 'EARLY_COUNTDOWN',30-elapsed
    if elapsed<35:return 'EARLY_PRESS',35-elapsed
    if elapsed<105:return 'LATE_COUNTDOWN',105-elapsed
    if elapsed<110:return 'LATE_PRESS',110-elapsed
    return 'RELEASE',120-elapsed
