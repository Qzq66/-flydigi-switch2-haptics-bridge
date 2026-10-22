"""Adapter contracts with fake libraries and sockets, never real I/O."""
import ast,json,pathlib,socket
from types import SimpleNamespace
from unittest.mock import patch
from bridge_network import NetworkConfig,DEFAULT_NETWORK
from bridge_windows import TimerResolution,XInputSource,load_owner
from bridge_protocol import BridgeFault
from bridge_input import NEUTRAL
from bridge_transport import Client
checks=[]
def check(name,ok):
    assert ok,name
    checks.append(dict(name=name,passed=True))
def raises(kind,fn):
    try:fn()
    except kind:return True
    return False
n=DEFAULT_NETWORK
check('default Windows network preserved',(n.bind_host,n.broadcast,n.port)==('192.168.137.1','192.168.137.255',49724))
custom=NetworkConfig('10.20.0.1','10.20.0.0/24',50000)
check('alternate subnet computes broadcast',custom.broadcast=='10.20.0.255')
for peer,expected in [(('10.20.0.20',50000),True),(('10.20.1.20',50000),False),(('10.20.0.20',49724),False),(('bad',50000),False),(('10.20.0.255',50000),False)]:
    check('peer filter '+repr(peer),custom.accepts(peer)==expected)
for values in [('10.21.0.1','10.20.0.0/24',50000),('10.20.0.0','10.20.0.0/24',50000),('10.20.0.1','10.20.0.0/24',0)]:
    check('invalid network rejected '+repr(values),raises(ValueError,lambda:NetworkConfig(*values)))
class Timer:
    def __init__(self,code=0):self.calls=[];self.code=code
    def timeBeginPeriod(self,n):self.calls.append(('begin',n));return self.code
    def timeEndPeriod(self,n):self.calls.append(('end',n));return 0
lib=Timer();t=TimerResolution(lib)
check('timer successful acquire',t.start())
t.start();t.close();t.close()
check('timer acquire and release once',lib.calls==[('begin',1),('end',1)])
lib=Timer(1);t=TimerResolution(lib);check('failed timer not active',not t.start());t.close()
check('failed timer is not released',lib.calls==[('begin',1)])
with patch('sys.platform','darwin'):
    check('timer hardware gate',raises(RuntimeError,lambda:TimerResolution().start()))
    check('HID owner hardware gate',raises(RuntimeError,load_owner))
gamepad=SimpleNamespace(buttons=0,lt=0,rt=0,lx=0,ly=0,rx=0,ry=0)
xi=SimpleNamespace(connected=lambda:[0],read=lambda slot:SimpleNamespace(gamepad=gamepad))
x=XInputSource(xi)
check('injected input reads neutral',x()==NEUTRAL)
check('input records changes',len(x.changes)==1 and x.nonneutral_reads==0)
xi.read=lambda slot:None
check('input disconnect faults',raises(BridgeFault,x))
check('ambiguous input rejected',raises(BridgeFault,lambda:XInputSource(SimpleNamespace(connected=lambda:[0,1]))))
class Sock:
    def bind(self,addr):self.bound=addr
    def settimeout(self,v):self.timeout=v
    def sendto(self,data,peer):self.peer=peer
    def recvfrom(self,n):raise socket.timeout()
    def close(self):self.closed=True
s=Sock()
with patch('bridge_transport.socket.socket',return_value=s):
    c=Client('10.20.0.20',123,network=custom)
check('transport binds configured interface',s.bound==('10.20.0.1',0))
c.poll();check('transport uses configured port',s.peer==('10.20.0.20',50000));c.close()
check('transport closes socket',s.closed)
for name in ('bridge_protocol.py','bridge_render.py'):
    tree=ast.parse(pathlib.Path(__file__).with_name(name).read_text())
    imports=[a.name.split('.')[0] for node in ast.walk(tree) if isinstance(node,ast.Import) for a in node.names]
    imports += [node.module for node in ast.walk(tree) if isinstance(node,ast.ImportFrom)]
    check(name+' has no platform/transport dependency',not set(imports)&{'socket','ctypes','subprocess','bridge_windows','bridge_transport','xinput_readonly'})
print(json.dumps(checks))
