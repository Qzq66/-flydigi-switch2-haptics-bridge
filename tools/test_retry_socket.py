"""Deterministic boundary checks; no hardware or real sockets."""
import pathlib,socket,sys
sys.path.insert(0,str(pathlib.Path(__file__).absolute().parents[1]/'handoff/2026-10-22/work'))
from bridge_retry_socket import RetrySocket
class Fake:
    def __init__(self,events=()):self.now=0;self.events=list(events);self.sent=[];self.timeout=0
    def sendto(self,data,peer):self.sent.append((bytes(data),peer,self.now));return len(data)
    def settimeout(self,value):self.timeout=value
    def recvfrom(self,*args):
        self.now+=self.timeout
        if self.events:
            event=self.events.pop(0)
            if event is not None:
                if isinstance(event,Exception):raise event
                return event
        raise socket.timeout()
checks=0
def check(ok):
    global checks
    assert ok;checks+=1
f=Fake([None,None,(b'reply',('pc',49724))]);r=RetrySocket(f,clock=lambda:f.now)
r.sendto(b'BHI2-same-sequence-and-input',('pc',49724));check(r.recvfrom(512)[0]==b'reply')
check(len(f.sent)==3);check(all(x[:2]==f.sent[0][:2] for x in f.sent));check(r.deadline==.06);check(r.retries==2)
f=Fake();r=RetrySocket(f,clock=lambda:f.now);r.sendto(b'BHE2-same-ack',('pc',49724))
try:r.recvfrom(512)
except socket.timeout:check(True)
else:raise AssertionError('Budget did not expire')
check(abs(f.now-.06)<1e-9);check(len(f.sent)==7);check(r.retries==6)
f=Fake([OSError('disconnect')]);r=RetrySocket(f,clock=lambda:f.now);r.sendto(b'query',('pc',49724))
try:r.recvfrom(512)
except OSError:check(len(f.sent)==1)
else:raise AssertionError('Transport error swallowed')
for options in ({'budget':.061},{'max_retries':7},{'interval':0}):
    try:RetrySocket(Fake(),**options)
    except ValueError:check(True)
    else:raise AssertionError('Invalid limit accepted')
print('PASSED bounded retry socket:',checks,'checks')
