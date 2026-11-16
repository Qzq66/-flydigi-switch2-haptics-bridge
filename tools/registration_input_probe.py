"""Bounded read/send/matching-reply observations, no packet or device mutation."""
import collections,hashlib,math,struct,time

def firmware_shape_valid(value):
    if type(value) is not bytes or len(value)!=9:return False
    if value[0]&~0xcf or value[1]&~0x0f or value[2]&~0xcf:return False
    for i in (3,6):
        x=value[i]|(value[i+1]&15)<<8;y=(value[i+1]>>4)|value[i+2]<<4
        if not 448<=x<=3648 or not 448<=y<=3648:return False
    return True

class InputProbe:
    LIMIT=32768;CHANGES=128
    def __init__(self,source,clock=time.perf_counter):
        self.source=source;self.clock=clock;self.reads=self.sends=self.replies=0
        self.changes=[];self.omitted_changes=0;self.last_read=None;self.last_send=None
        self.categories={k:dict(reads=0,sends=0,replies=0) for k in ('L','R','LR','A','neutral','other')}
        self.sha=hashlib.sha256();self.failed=False
    def category(self,v):
        buttons=v[:3]
        return {bytes.fromhex('000040'):'L',bytes.fromhex('400000'):'R',bytes.fromhex('400040'):'LR',bytes.fromhex('080000'):'A'}.get(buttons,'neutral' if v==bytes.fromhex('000000000880000880') else 'other')
    def __call__(self):
        if self.failed or self.reads>=self.LIMIT:raise ValueError('Input observation budget or prior fault')
        v=self.source()
        if not firmware_shape_valid(v):self.failed=True;raise ValueError('Input fails installed firmware shape check')
        self.reads+=1;self.categories[self.category(v)]['reads']+=1
        if v!=self.last_read:
            if len(self.changes)<self.CHANGES:self.changes.append(dict(read_index=self.reads,at=self.clock(),input_hex=v.hex()))
            else:self.omitted_changes+=1
        self.last_read=v;return v
    def sent(self,data):
        if data[:4]!=b'BHI2':self.last_send=None;return
        if len(data)!=36:raise ValueError('Input packet length')
        number=struct.unpack_from('<I',data,4)[0];seq=struct.unpack_from('<I',data,20)[0];v=data[24:33]
        if number!=seq or v!=self.last_read or not firmware_shape_valid(v):self.failed=True;raise ValueError('Read/send input mismatch')
        if self.sends>=self.LIMIT:self.failed=True;raise ValueError('Input send budget')
        self.sends+=1;self.sha.update(v);self.categories[self.category(v)]['sends']+=1;self.last_send=(number,v)
    def replied(self,number):
        if self.last_send is not None and self.last_send[0]==number:
            self.replies+=1;self.categories[self.category(self.last_send[1])]['replies']+=1
    def snapshot(self):
        return dict(reads=self.reads,successful_input_sends=self.sends,matching_request_replies=self.replies,categories=self.categories,
            changes=list(self.changes),omitted_changes=self.omitted_changes,change_limit=self.CHANGES,call_limit=self.LIMIT,
            ordered_sent_input_sha256=self.sha.hexdigest(),fault_latched=self.failed,
            scope='Sendto success and matching request reply do not prove Pico applied input or Switch accepted USB report.',
            packet_payload_recorded=False,peer_or_session_recorded=False)

class ObservedSocket:
    def __init__(self,sock,probe):self.sock=sock;self.probe=probe
    def __getattr__(self,name):return getattr(self.sock,name)
    def sendto(self,data,peer):
        n=self.sock.sendto(data,peer)
        if n!=len(data):raise RuntimeError('Partial UDP submission')
        self.probe.sent(data);return n

class RegistrationClient:
    def __init__(self,client,probe):
        self.client=client;self.probe=probe;client.sock=ObservedSocket(client.sock,probe)
    def __getattr__(self,name):return getattr(self.client,name)
    def poll(self,*a,**k):
        frame=self.client.poll(*a,**k)
        if frame is not None:self.probe.replied(self.client.request)
        return frame
