"""Exact lab-043 RAM identity only; never opens the Flydigi receiver."""
import ctypes as C,importlib.util,json,pathlib,socket,struct,time
ROOT=pathlib.Path(__file__).absolute().parents[1];WORK=ROOT/'handoff/2026-10-22/work'

def exact_043(product,serial,usage_page,usage):
    return product=='Bridge Pro Live 043' and serial=='BPCAP-RP2350-LOCAL-043' and usage_page==1 and usage==4

class Probe:
    def __init__(self):
        spec=importlib.util.spec_from_file_location('neutral_ram_base',WORK/'test-pico-capture-v035-ram.py')
        self.m=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.m)
    def open(self,profile='ram'):
        if profile not in ('ram','flash'):raise ValueError('Expected explicit RAM or Flash profile')
        m=self.m;m.lib.hid_init();until=time.monotonic()+20
        while time.monotonic()<until:
            vid,pid=(0xcafe,0x4012) if profile=='ram' else (0x057e,0x2009)
            head=m.lib.hid_enumerate(vid,pid);matches=[]
            try:
                node=head
                while node:
                    d=node.contents
                    if exact_043(d.product_string,d.serial_number,d.usage_page,d.usage):matches.append(bytes(d.path))
                    node=d.next
            finally:
                if head:m.lib.hid_free_enumeration(head)
            if matches:break
            time.sleep(.1)
        if len(matches)!=1:raise ValueError('Exactly one lab-043 candidate required')
        m.handle=m.lib.hid_open_path(matches[0])
        if not m.handle:raise OSError('Cannot open lab-043')
        expected=b'BCAP\5\0\0'+bytes([int(profile=='ram')])
        if m.read_virtual(0x9000,8)!=expected:raise ValueError('Not initial capture firmware with the requested memory profile')
        m.verified=True;m.allow_lr=True
    def endpoint(self,timeout=40):
        until=time.monotonic()+timeout;last=None
        while time.monotonic()<until:
            d=self.m.read_range(0x9200,48)
            if d[:4]!=b'BRD2':raise ValueError('Transport identity mismatch')
            link=struct.unpack_from('<i',d,36)[0];ip=socket.inet_ntoa(d[8:12]);last=(link,ip)
            if link==3 and ip.startswith('192.168.137.') and ip!='192.168.137.1':
                return dict(ip=ip,session=struct.unpack_from('<Q',d,40)[0])
            time.sleep(.15)
        raise TimeoutError('043 WiFi join did not complete: '+str(last))
    def close(self):
        if self.m.handle:self.m.lib.hid_close(self.m.handle);self.m.handle=None
        self.m.lib.hid_exit()
