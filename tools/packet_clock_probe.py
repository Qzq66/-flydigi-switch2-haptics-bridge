"""Bounded private socket observations; never accepts, drops or changes a packet."""
import hashlib,json,pathlib,time
from capture_clock import anchor

class PacketClockProbe:
    def __init__(self,utc,clock=time.perf_counter,limit=100000):
        self.utc=utc;self.clock=clock;self.limit=limit;self.rows=[]
        self.anchors=[anchor(utc,clock)];self.errors=0;self.overflow=0;self.max_cost=0.

    def record(self,direction,data,at):
        begin=self.clock()
        try:
            if len(self.rows)>=self.limit:self.overflow+=1;return
            self.rows.append(dict(direction=direction,at=at,size=len(data),sha256=hashlib.sha256(data).hexdigest()))
        except Exception:self.errors+=1
        finally:self.max_cost=max(self.max_cost,self.clock()-begin)

    def finish(self,path):
        self.anchors.append(anchor(self.utc,self.clock))
        value=dict(version=1,anchors=self.anchors,rows=self.rows,errors=self.errors,overflow=self.overflow,
            maximum_observer_seconds=self.max_cost,clock='same_process_perf_counter',motor_commands=0)
        data=json.dumps(value,separators=(',',':')).encode('utf-8')
        with pathlib.Path(path).open('xb') as f:f.write(data)
        return dict(rows=len(self.rows),errors=self.errors,overflow=self.overflow,
            maximum_observer_seconds=self.max_cost,private_trace_sha256=hashlib.sha256(data).hexdigest(),
            contains_payload=False,clock_anchors=len(self.anchors))

class PacketClockSocket:
    def __init__(self,sock,probe):self.sock=sock;self.probe=probe
    def __getattr__(self,name):return getattr(self.sock,name)
    def sendto(self,data,peer):
        result=self.sock.sendto(data,peer);at=self.probe.clock()
        self.probe.record('send',data,at);return result
    def recvfrom(self,size):
        data,peer=self.sock.recvfrom(size);at=self.probe.clock()
        self.probe.record('receive',data,at);return data,peer
