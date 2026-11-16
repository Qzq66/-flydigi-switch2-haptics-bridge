"""Independent12ms receive-budget candidate, same accepted wire and event rules."""
import pathlib,sys,time,socket,struct
ROOT=pathlib.Path(__file__).absolute().parents[1]
sys.path.insert(0,str(ROOT/'handoff/2026-10-22/work'))
from bridge_transport import Client as AcceptedClient
from bridge_protocol import BridgeFault,unpack

class ShortWaitClient(AcceptedClient):
    RECEIVE_BUDGET_SECONDS=.012

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.clock=time.perf_counter;self.receive_budget=self.RECEIVE_BUDGET_SECONDS
        self.sock.settimeout(self.receive_budget)
        self.deadline_expirations=0;self.late_matching_replies=0;self.stale_replies=0

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
        started=self.clock();deadline=started+self.receive_budget
        while True:
            remaining=deadline-self.clock()
            if remaining<=0:self.deadline_expirations+=1;return None
            self.sock.settimeout(remaining)
            try:data,peer=self.sock.recvfrom(512)
            except socket.timeout:self.deadline_expirations+=1;return None
            matching=peer==(self.ip,self.network.port) and len(data)>=20 and struct.unpack_from('<I',data,16)[0]==self.request
            if self.clock()>deadline:
                self.deadline_expirations+=1;self.late_matching_replies+=int(matching);return None
            if peer!=(self.ip,self.network.port):continue
            if not matching:self.stale_replies+=1;continue
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
            frame['events']=accepted;frame['received_at']=self.clock();frame['rtt_ms']=(frame['received_at']-started)*1000
            if final_ack:self.terminal_ack_replied=bool(frame['flags']&16)
            return frame
