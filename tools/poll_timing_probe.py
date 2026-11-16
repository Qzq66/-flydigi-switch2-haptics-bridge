"""Observe unchanged input/socket calls, retaining bounded incident context."""
import collections,time
from game_transport_diagnostics import ObservedClient

class SocketProbe:
    def __init__(self,sock,observe):self.sock=sock;self.observe=observe
    def __getattr__(self,name):return getattr(self.sock,name)
    def sendto(self,*args,**kwargs):return self.observe('send',self.sock.sendto,*args,**kwargs)
    def recvfrom(self,*args,**kwargs):return self.observe('receive',self.sock.recvfrom,*args,**kwargs)

class DetailedClient(ObservedClient):
    def __init__(self,client,clock=time.perf_counter):
        super().__init__(client,clock)
        self.current=None;self.last_end=None;self.details=collections.deque(maxlen=64)
        self.incidents=collections.deque(maxlen=32)
        self.maxima=dict(input=0.,send=0.,receive=0.,between_polls=0.,unattributed=0.)
        client.sock=SocketProbe(client.sock,self.measure)
        if client.input_source is not None:
            source=client.input_source
            client.input_source=lambda:self.measure('input',source)

    def measure(self,kind,call,*args,**kwargs):
        began=self.clock();error=None
        try:return call(*args,**kwargs)
        except BaseException as exc:error=type(exc).__name__;raise
        finally:
            duration=self.clock()-began
            self.maxima[kind]=max(self.maxima[kind],duration)
            if self.current is not None:
                self.current['stage_seconds'][kind]+=duration
                self.current['stage_calls'][kind]+=1
                self.current['operations'].append(dict(kind=kind,duration=duration,error_type=error))

    def poll(self,*args,**kwargs):
        start=self.clock();last_received=self.last_received
        idle=None if self.last_end is None else max(0.,start-self.last_end)
        if idle is not None:self.maxima['between_polls']=max(self.maxima['between_polls'],idle)
        self.current=dict(start=start,between_polls=idle,stage_seconds=dict(input=0.,send=0.,receive=0.),
            stage_calls=dict(input=0,send=0,receive=0),operations=collections.deque(maxlen=16))
        frame=None;error=None
        try:
            frame=super().poll(*args,**kwargs);return frame
        except BaseException as exc:error=type(exc).__name__;raise
        finally:
            end=self.clock();item=dict(self.current);item['operations']=list(item['operations'])
            duration=end-start;other=max(0.,duration-sum(item['stage_seconds'].values()))
            self.maxima['unattributed']=max(self.maxima['unattributed'],other)
            gap=None if frame is None or last_received is None else frame['received_at']-last_received
            item.update(end=end,duration=duration,unattributed_seconds=other,response_gap=gap,
                outcome='error' if error else ('timeout' if frame is None else 'frame'),error_type=error)
            self.details.append(item)
            if error or frame is None or gap is not None and gap>.080 or idle is not None and idle>.020 or duration>.040:
                self.incidents.append(item)
            self.last_end=end;self.current=None

    def snapshot(self):
        result=super().snapshot()
        result.update(stage_maximum_seconds=dict(self.maxima),detailed_recent=list(self.details),
            timing_incidents=list(self.incidents),timing_scope='Receive-call duration includes OS wait and scheduling; it does not isolate radio latency. No packet bodies or credentials recorded.')
        return result
