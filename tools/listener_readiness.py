"""Wait for the child's post-neutral discovery phase before instructing a USB swap."""
import json,time

def wait_for_discovery(proc,phase,timeout=15,clock=time.monotonic,pause=time.sleep):
    end=clock()+timeout
    while clock()<end:
        if proc.poll() is not None:raise RuntimeError('Child exited before neutral check and discovery readiness')
        try:status=json.loads(phase.read_text(encoding='utf-8'))
        except (OSError,ValueError):status={}
        if status.get('phase')=='DISCOVERING' and status.get('clock')=='monotonic':
            if proc.poll() is not None:raise RuntimeError('Child exited before readiness confirmation')
            return
        pause(.05)
    raise TimeoutError('No post-neutral discovery readiness; keep Pico on PC BOOTSEL')
