"""Opt-in diagnostic retransmission; packet validation remains in Client."""
import socket,time

class RetrySocket:
    def __init__(self,inner,interval=.008,budget=.06,max_retries=6,clock=time.perf_counter):
        if not 0<interval<=budget<=.06 or type(max_retries) is not int or not 0<=max_retries<=6:
            raise ValueError('Retries must fit the existing 60ms budget')
        self.inner=inner;self.interval=interval;self.budget=budget;self.maximum=max_retries;self.clock=clock
        self.query=None;self.retries=0;self.used=0;self.deadline=0
    def __getattr__(self,name):return getattr(self.inner,name)
    def sendto(self,data,peer):
        self.deadline=self.clock()+self.budget;self.used=0;self.query=(bytes(data),peer)
        return self.inner.sendto(data,peer)
    def recvfrom(self,*args):
        if self.query is None:raise RuntimeError('No pending request')
        while True:
            remaining=self.deadline-self.clock()
            if remaining<=0:raise socket.timeout('Existing request budget exhausted')
            self.inner.settimeout(min(self.interval,remaining) if self.used<self.maximum else remaining)
            try:return self.inner.recvfrom(*args)
            except socket.timeout:
                if self.clock()>=self.deadline or self.used>=self.maximum:raise
                self.inner.sendto(*self.query);self.used+=1;self.retries+=1
