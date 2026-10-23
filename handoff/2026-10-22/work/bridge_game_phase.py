"""Shared monotonic UI deadline; UI can request once, child remains authoritative."""
import math

def remaining(status,now):
    deadline=status.get('deadline_monotonic')
    if status.get('clock')!='monotonic' or type(deadline) not in (int,float) or not math.isfinite(deadline):return None
    return max(0,deadline-now)

def can_arm(status,now):
    seconds=remaining(status,now)
    return status.get('phase')=='INPUT_READY' and seconds is not None and seconds>5
