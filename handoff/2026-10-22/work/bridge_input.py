"""Physical-position XInput mapping to Pro buttons/sticks. No controller writes."""
import struct
NEUTRAL=bytes.fromhex('000000000880000880')
def pack_axes(x,y):return bytes((x&255,((x>>8)&15)|((y&15)<<4),(y>>4)&255))
def convert(g):
    b=g.buttons;right=shared=left=0
    for mask,bit in ((0x1000,2),(0x2000,3),(0x4000,0),(0x8000,1),(0x0200,6)):
        if b&mask:right|=1<<bit
    for mask,bit in ((0x20,0),(0x10,1),(0x80,2),(0x40,3)):
        if b&mask:shared|=1<<bit
    for mask,bit in ((2,0),(1,1),(8,2),(4,3),(0x100,6)):
        if b&mask:left|=1<<bit
    if g.lt>30:left|=128
    if g.rt>30:right|=128
    def stick(x,y,deadzone):
        if x*x+y*y<=deadzone*deadzone:return (2048,2048)
        return tuple(max(448,min(3648,2048+round(v*1600/32768))) for v in (x,y))
    return bytes((right,shared,left))+pack_axes(*stick(g.lx,g.ly,7849))+pack_axes(*stick(g.rx,g.ry,8689))

class XInputSource:
    def __init__(self):
        import xinput_readonly as xi
        from bridge_runtime import BridgeFault
        self.xi=xi;self.fault=BridgeFault;slots=xi.connected()
        if len(slots)!=1:raise BridgeFault('Exactly one PC XInput controller required')
        self.slot=slots[0]
        self.changes=[];self.previous=None;self.nonneutral_reads=0
    def __call__(self):
        state=self.xi.read(self.slot)
        if state is None:raise self.fault('XInput source disconnected; relay stopped')
        value=convert(state.gamepad)
        if value!=NEUTRAL:self.nonneutral_reads+=1
        if value!=self.previous:
            import time
            if len(self.changes)<64:self.changes.append(dict(at=time.perf_counter(),pro_input=value.hex()))
            self.previous=value
        return value
