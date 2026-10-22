"""UDP transport; sockets are created only by explicit Client construction."""
import socket,struct,secrets,time
from bridge_protocol import BridgeFault,unpack
from bridge_network import DEFAULT_NETWORK

class Client:
    def __init__(self,ip,session,input_source=None,network=DEFAULT_NETWORK):
        self.network=network;self.ip=ip;self.session=session;self.request=secrets.randbits(32);self.ack=0xffffffff
        self.boot=None;self.expected=0;self.last_at=None;self.received=0;self.duplicates=0
        self.terminal_received=False;self.terminal_ack_replied=False;self.draining=False
        self.input_source=input_source
        self.sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);self.sock.bind((network.bind_host,0));self.sock.settimeout(.06)
    def poll(self,final_ack=False):
        if final_ack and not self.terminal_received:raise BridgeFault('cannot acknowledge unseen stream end')
        self.request=(self.request+1)&0xffffffff
        magic=b'BHE2' if final_ack else (b'BHI2' if self.input_source is not None and not self.draining else b'BHP2')
        query=struct.pack('<4sIQI',magic,self.request,self.session,self.ack)
        if magic==b'BHI2':
            state=self.input_source()
            if len(state)!=9:raise BridgeFault('invalid input relay size')
            query+=struct.pack('<I9s3x',self.request,state)
        self.sock.sendto(query,(self.ip,self.network.port))
        started=time.perf_counter()
        while time.perf_counter()-started<.06:
            try:data,peer=self.sock.recvfrom(512)
            except socket.timeout:return None
            if peer!=(self.ip,self.network.port):continue
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

