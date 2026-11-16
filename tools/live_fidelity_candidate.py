# SPDX-License-Identifier: GPL-2.0-only
"""Streaming renderer candidate only: no sockets, device writes or live entry hook.

Scheduling follows the existing experimental 64ms buffer / 5ms parameter groups.
One bilateral episode completes to permanent mute; caller must stop actual output.
The final block is returned in full; only the following None requests stopping.
Any future hardware adapter must let that final 8ms block drain before disabling.
"""
import heapq,math,pathlib,sys
sys.path.insert(0,str(pathlib.Path(__file__).absolute().parents[1]/'handoff/2026-10-22/work'))
from switch_hd_decode import Decoder
from bridge_protocol import BridgeFault

class LiveFidelityRenderer:
    def __init__(self):
        self.decoders=[Decoder(),Decoder()];self.anchor=None;self.last_received=None;self.last_source=None
        self.upstream=False;self.next_sequence=0;self.pending=[];self.order=0;self.last_due=[None,None]
        self.values=[[0.,160.,0.,320.],[0.,160.,0.,320.]];self.phases=[[0.,0.],[0.,0.]]
        self.armed=False;self.armed_at=None;self.output_start=None;self.rendered_until=None;self.muted_reason=None;self.fault=None
        self.active_total=[0,0];self.active_run=[0,0];self.episodes=[0,0];self.was_active=[False,False];self.dose=[0,0]
        self.maximum_offset=0;self.blocks=0

    def fail(self,why):
        self.fault=why;self.pending.clear();self.values=[[0.,160.,0.,320.],[0.,160.,0.,320.]]
        raise BridgeFault(why)

    def mute(self,why):
        self.muted_reason=why;self.pending.clear();self.values=[[0.,160.,0.,320.],[0.,160.,0.,320.]]

    def arm(self,now):
        if self.fault:raise BridgeFault(self.fault)
        if self.armed or self.muted_reason:self.fail('explicit arm is one-shot')
        if not self.upstream or self.last_received is None or not math.isfinite(now) or not 0<=now-self.last_received<=.080:self.fail('fresh upstream heartbeat required before arm')
        self.armed=True;self.armed_at=now;self.output_start=now+.064;self.pending.clear();self.last_due=[None,None]
        return self.output_start

    def feed(self,frame):
        if self.fault:raise BridgeFault(self.fault)
        now=frame['received_at'];processed=frame.get('processed_at',now)
        if not all(math.isfinite(v) for v in (now,processed)) or processed<now:self.fail('invalid receiver time')
        if self.last_received is not None and now<self.last_received:self.fail('receiver clock reversed')
        stamp=frame['source_us']
        if self.last_source is not None and ((stamp-self.last_source+0x80000000)&0xffffffff)-0x80000000<0:self.fail('source clock reversed')
        self.last_source=stamp;self.last_received=now
        if frame['flags']&8:
            if not self.muted_reason:self.mute('stream ended')
            return
        if frame['flags']&2:self.upstream=True
        elif self.upstream:self.fail('USB upstream stopped')
        if self.anchor is None:self.anchor=(stamp,now)
        if self.muted_reason:return
        if self.armed and not frame['flags']&4:
            self.mute('source vibration disabled');return
        source,local=self.anchor
        for event in frame['events']:
            if event['sequence']!=self.next_sequence:self.fail('source sequence gap')
            self.next_sequence+=1
            raw=event['motors']
            if len(raw)!=8:self.fail('invalid motor field')
            if (stamp-event['at_us'])&0xffffffff>=0x80000000:self.fail('future source event')
            for side,word in enumerate((raw[:4],raw[4:])):
                for i,s in enumerate(self.decoders[side].decode(word)['samples']):
                    if not self.armed:continue
                    if not s['state_complete']:self.fail('unknown decoder state')
                    values=[s[k] for k in ('low_amplitude','low_hz','high_amplitude','high_hz')]
                    if not all(math.isfinite(v) for v in values):self.fail('non-finite decoded parameter')
                    if any(a and f>=500 for a,f in ((values[0],values[1]),(values[2],values[3]))):self.fail('active frequency outside 1kHz band')
                    if 96*(values[0]+values[2])>12:self.fail('conservative amplitude bound')
                    signed=((event['at_us']-source+0x80000000)&0xffffffff)-0x80000000
                    due=local+signed/1e6+.064+i*.005
                    if due<self.output_start-1e-9:continue
                    previous=self.last_due[side]
                    if previous is not None and (due<previous[0]-1e-9 or abs(due-previous[0])<1e-9 and values!=previous[1]):self.fail('ambiguous parameter-group order')
                    self.last_due[side]=(due,values)
                    # Neutral updates also affect envelope timing: never silently
                    # discard or retime either active or neutral late groups.
                    if due<processed-1e-9 or self.rendered_until is not None and due<self.rendered_until-1e-9:self.fail('parameter arrived after playback deadline')
                    self.order+=1;heapq.heappush(self.pending,(due,self.order,side,values))
                    if len(self.pending)>512:self.fail('render queue capacity')

    def block(self,now,observed_at=None):
        if self.fault:raise BridgeFault(self.fault)
        # The immutable PCM grid may be slightly behind real dispatch time.
        # A freshly collected packet can therefore be newer than `now`.
        observed=now if observed_at is None else observed_at
        if not math.isfinite(observed) or observed<now:self.fail('invalid dispatch time')
        if self.last_received is None or not 0<=observed-self.last_received<=.080+1e-9:self.fail('wire heartbeat timeout')
        if not self.armed:return [[128]*8,[128]*8]
        if self.muted_reason:return None
        if observed-self.armed_at>15:self.fail('bounded armed window expired')
        expected=self.output_start if self.rendered_until is None else self.rendered_until
        if abs(now-expected)>1e-6:self.fail('non-contiguous output clock; no catch-up')
        output=[[],[]]
        for i in range(8):
            at=now+i*.001
            while self.pending and self.pending[0][0]<=at+1e-9:
                _,_,side,values=heapq.heappop(self.pending);self.values[side]=values
            for side in (0,1):
                a,f,b,g=self.values[side];active=bool(a or b)
                if active and not self.was_active[side]:
                    if self.episodes[side]>=1:self.fail('single-episode cap')
                    self.episodes[side]+=1
                run=self.active_run[side]+1 if active else 0
                if run>320 or self.active_total[side]+int(active)>320:self.fail('320ms source activity cap')
                value=round(96*(a*math.sin(self.phases[side][0])+b*math.sin(self.phases[side][1])))
                if abs(value)>12 or self.dose[side]+value*value>8000:self.fail('sample amplitude or cumulative code-energy cap')
                self.active_run[side]=run;self.active_total[side]+=int(active);self.was_active[side]=active;self.dose[side]+=value*value
                output[side].append(128+value);self.maximum_offset=max(self.maximum_offset,abs(value))
                self.phases[side][0]=(self.phases[side][0]+2*math.pi*f/1000)%(2*math.pi)
                self.phases[side][1]=(self.phases[side][1]+2*math.pi*g/1000)%(2*math.pi)
        self.blocks+=1;self.rendered_until=now+.008
        if all(self.episodes) and all(not(a or b) for a,f,b,g in self.values):self.mute('single bilateral episode completed')
        return output
