# SPDX-License-Identifier: GPL-2.0-only
# Uses switch_hd_decode.py, adapted from MissionControl; see its license notice.
"""Bounded prototype wire receiver and renderer; this module never opens HID."""
import socket,struct,zlib,secrets,time,heapq,math
from switch_hd_decode import Decoder

class BridgeFault(RuntimeError):pass

def unpack(data,session,request):
    if len(data)<36 or data[:4]!=b'BHR2':raise BridgeFault('wire identity')
    magic,version,flags,size,nonce,number,boot,stamp,count,dropped=struct.unpack_from('<4sBBHQIIIHH',data)
    if version!=2 or flags&~31 or size!=len(data) or len(data)!=36+count*16 or count>8:raise BridgeFault('wire bounds')
    if flags&8 and flags&6:raise BridgeFault('terminal stream still active')
    if flags&16 and (not flags&8 or count):raise BridgeFault('invalid complete marker')
    if nonce!=session or number!=request:raise BridgeFault('wire session or request')
    if zlib.crc32(data[:-4])!=struct.unpack_from('<I',data,len(data)-4)[0]:raise BridgeFault('wire CRC')
    if dropped:raise BridgeFault('source queue overflow')
    events=[]
    for i in range(count):
        at,seq,motors=struct.unpack_from('<II8s',data,32+i*16)
        if (stamp-at)&0xffffffff>=0x80000000:raise BridgeFault('future source timestamp')
        events.append(dict(at_us=at,sequence=seq,motors=motors))
    return dict(flags=flags,boot=boot,source_us=stamp,events=events)

class Client:
    def __init__(self,ip,session,input_source=None):
        self.ip=ip;self.session=session;self.request=secrets.randbits(32);self.ack=0xffffffff
        self.boot=None;self.expected=0;self.last_at=None;self.received=0;self.duplicates=0
        self.terminal_received=False;self.terminal_ack_replied=False;self.draining=False
        self.input_source=input_source
        self.sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);self.sock.bind(('192.168.137.1',0));self.sock.settimeout(.06)
    def poll(self,final_ack=False):
        if final_ack and not self.terminal_received:raise BridgeFault('cannot acknowledge unseen stream end')
        self.request=(self.request+1)&0xffffffff
        magic=b'BHE2' if final_ack else (b'BHI2' if self.input_source is not None and not self.draining else b'BHP2')
        query=struct.pack('<4sIQI',magic,self.request,self.session,self.ack)
        if magic==b'BHI2':
            state=self.input_source()
            if len(state)!=9:raise BridgeFault('invalid input relay size')
            query+=struct.pack('<I9s3x',self.request,state)
        self.sock.sendto(query,(self.ip,49724))
        started=time.perf_counter()
        while time.perf_counter()-started<.06:
            try:data,peer=self.sock.recvfrom(512)
            except socket.timeout:return None
            if peer!=(self.ip,49724):continue
            # Old datagrams may arrive after a request timeout; never consume them.
            if len(data)<20 or struct.unpack_from('<I',data,16)[0]!=self.request:continue
            frame=unpack(data,self.session,self.request)
            if self.boot is not None and self.boot!=frame['boot']:raise BridgeFault('Pico restarted; explicit new session required')
            if self.draining and not frame['flags']&8:raise BridgeFault('stream resumed after terminal marker')
            if self.terminal_received and not frame['flags']&16:raise BridgeFault('complete stream marker regressed')
            if final_ack and not frame['flags']&16:raise BridgeFault('end confirmation missing complete marker')
            if frame['flags']&8:self.draining=True
            self.boot=frame['boot'];accepted=[]
            if frame['flags']&16:self.terminal_received=True
            for event in frame['events']:
                delta=(event['sequence']-self.expected)&0xffffffff
                if delta>=0x80000000:self.duplicates+=1;continue
                if delta:raise BridgeFault('event sequence gap')
                if self.last_at is not None and (event['at_us']-self.last_at)&0xffffffff>=0x80000000:raise BridgeFault('source clock reversed')
                self.last_at=event['at_us'];self.ack=event['sequence'];self.expected=(self.expected+1)&0xffffffff
                accepted.append(event);self.received+=1
            frame['events']=accepted;frame['received_at']=time.perf_counter();frame['rtt_ms']=(frame['received_at']-started)*1000
            if final_ack:self.terminal_ack_replied=bool(frame['flags']&16)
            return frame
        return None
    def close(self):self.sock.close()
    def confirm_end(self):
        for _ in range(3):
            frame=self.poll(final_ack=True)
            if frame is not None:return frame
        return None

def collect_frames(client,publish,stopped,pause=time.sleep):
    """Collect frames without owning hardware; stop playback before end retries.

    A complete marker is not published as successful until BHE2 is answered.
    Publish a draining-only marker first so an output consumer can stop while
    the bounded network acknowledgement is in progress.
    """
    while not stopped():
        frame=client.poll()
        if frame:
            if frame['flags']&16:
                publish(dict(frame,flags=frame['flags']&~16))
                reply=client.confirm_end()
                if reply is None or not client.terminal_ack_replied:
                    raise BridgeFault('stream end acknowledgement timeout')
                publish(frame)
                return
            publish(frame)
        pause(.004)

class Renderer:
    """64ms experimental jitter buffer; 5ms parameter groups, 1kHz PCM.

    Opt-in prompt_ms=120 maps an active edge to a calibrated notification,
    160Hz left/320Hz right, with an explicitly selected sample-code bound.
    Source neutral ends the original group but not this bounded notification;
    vibration disable, USB loss, faults and heartbeat timeout always cancel it.

    This does not claim measured Nintendo group timing or physical fidelity.
    A fault permanently stops this instance. No automatic resume.
    """
    def __init__(self,prompt_ms=0,prompt_offset=3,game_pilot=False):
        if prompt_ms not in (0,120):raise ValueError('Only original or calibrated 120ms prompt mode is supported')
        if prompt_offset not in (3,5,8,12) or (not prompt_ms and prompt_offset!=3):raise ValueError('Unsupported explicit prompt amplitude')
        self.prompt_offset=prompt_offset
        if game_pilot and prompt_ms!=120:raise ValueError('Game pilot requires bounded notification mode')
        self.source_limits=(1000,3000) if game_pilot else (40,100)
        self.prompt_ms=prompt_ms;self.prompt_remaining=[0,0];self.prompt_counts=[0,0];self.prompt_phase=[0,0];self.source_was_active=[False,False]
        self.source_active_total=[0,0];self.source_active_run=[0,0]
        self.decoders=[Decoder(),Decoder()];self.anchor=None;self.last_received=None;self.upstream_seen=False
        self.pending=[];self.order=0;self.values=[[0,160,0,320],[0,160,0,320]];self.phases=[[0,0],[0,0]]
        self.active_total=[0,0];self.active_run=[0,0];self.fault=None;self.samples_rendered=0;self.rendered_until=None
    def fail(self,why):
        self.fault=why;self.pending=[];self.values=[[0,160,0,320],[0,160,0,320]];self.prompt_remaining=[0,0];raise BridgeFault(why)
    def feed(self,frame):
        if self.fault:raise BridgeFault(self.fault)
        now=frame['received_at'];processed=frame.get('processed_at',now);self.last_received=now
        if frame['flags']&2:self.upstream_seen=True
        elif self.upstream_seen:self.fail('USB upstream stopped')
        if self.anchor is None:self.anchor=(frame['source_us'],now)
        source,local=self.anchor
        for event in frame['events']:
            for side,raw in enumerate((event['motors'][:4],event['motors'][4:])):
                for i,sample in enumerate(self.decoders[side].decode(raw)['samples']):
                    values=[sample[k] for k in ('low_amplitude','low_hz','high_amplitude','high_hz')]
                    if not sample['state_complete']:self.fail('unknown decoder state')
                    if not all(math.isfinite(v) for v in values):self.fail('non-finite decoded value')
                    if not self.prompt_ms and any(amp and freq>=500 for amp,freq in ((values[0],values[1]),(values[2],values[3]))):self.fail('frequency exceeds 1kHz PCM Nyquist bound')
                    # Preserve every group; never keep just the first group.
                    signed=((event['at_us']-source+0x80000000)&0xffffffff)-0x80000000
                    due=local+signed/1e6+.064+i*.005
                    if not frame['flags']&4:values=[0,160,0,320]
                    if due<processed-1e-9 and (values[0] or values[2]):self.fail('active sample expired before frame processing')
                    if self.rendered_until is not None and due<self.rendered_until-1e-9 and (values[0] or values[2]):
                        self.fail('active sample arrived after samples already sent')
                    if due<now-.008:
                        if values[0] or values[2]:self.fail('active sample arrived after playback deadline')
                        continue
                    self.order+=1;heapq.heappush(self.pending,(due,self.order,side,values))
                    if len(self.pending)>512:self.fail('render queue capacity')
        if not frame['flags']&4:
            self.values=[[0,160,0,320],[0,160,0,320]];self.pending=[]
            self.prompt_remaining=[0,0];self.source_was_active=[False,False]
    def block(self,now):
        if self.fault:raise BridgeFault(self.fault)
        if self.last_received is None or now-self.last_received>.080:self.fail('wire heartbeat timeout')
        if self.rendered_until is not None and abs(now-self.rendered_until)>1e-6:self.fail('non-contiguous output sample clock')
        result=[[],[]]
        for i in range(8):
            at=now+i*.001
            while self.pending and self.pending[0][0]<=at+1e-9:
                _,_,side,values=heapq.heappop(self.pending);self.values[side]=values
            for side in (0,1):
                a,f,b,g=self.values[side];active=bool(a or b)
                self.source_active_run[side]=self.source_active_run[side]+1 if active else 0
                self.source_active_total[side]+=active
                if self.source_active_run[side]>self.source_limits[0] or self.source_active_total[side]>self.source_limits[1]:self.fail('first-test active energy duration cap')
                if self.prompt_ms:
                    # Explicit notification mapping, not a faithful extension of
                    # Nintendo frequency/amplitude. Overlap never extends a pulse.
                    if active and not self.source_was_active[side] and not self.prompt_remaining[side]:
                        if self.prompt_counts[side]>=3:self.fail('calibrated prompt count cap')
                        self.prompt_counts[side]+=1;self.prompt_remaining[side]=120;self.prompt_phase[side]=0
                    self.source_was_active[side]=active
                    output_active=self.prompt_remaining[side]>0
                    value=self.prompt_offset*math.sin(self.prompt_phase[side]) if output_active else 0
                    result[side].append(128+round(value))
                    if output_active:
                        self.prompt_remaining[side]-=1
                        self.prompt_phase[side]=(self.prompt_phase[side]+2*math.pi*(160 if side==0 else 320)/1000)%(2*math.pi)
                else:
                    output_active=active
                    value=a*math.sin(self.phases[side][0])+b*math.sin(self.phases[side][1])
                    result[side].append(128+round(5*max(-1,min(1,value))))
                self.active_run[side]=self.active_run[side]+1 if output_active else 0
                self.active_total[side]+=output_active
                self.phases[side][0]=(self.phases[side][0]+2*math.pi*f/1000)%(2*math.pi)
                self.phases[side][1]=(self.phases[side][1]+2*math.pi*g/1000)%(2*math.pi)
        self.samples_rendered+=8;self.rendered_until=now+.008;return result
