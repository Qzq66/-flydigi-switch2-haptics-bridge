import pathlib,sys,unittest,struct,zlib
from unittest import mock
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'handoff/2026-10-22/work'))
import bridge_transport as original
import receive_budget12_transport as candidate
class Clock:
    def __init__(self):self.now=0.
    def __call__(self):return self.now
class Tests(unittest.TestCase):
    def test_source_diff_only_budget(self):
        self.assertEqual((ROOT/'tools/receive_budget12_transport.py').read_text().replace('.012','.06'),(ROOT/'handoff/2026-10-22/work/bridge_transport.py').read_text())
    def run_client(self,module,delay,timeout=False):
        c=Clock()
        class Sock:
            def bind(self,*a):pass
            def settimeout(self,n):self.budget=n
            def sendto(self,data,peer):self.data=data;self.peer=peer;return len(data)
            def recvfrom(self,n):
                c.now+=delay
                if timeout:raise module.socket.timeout()
                req=struct.unpack_from('<I',self.data,4)[0]
                data=struct.pack('<4sBBHQIIIHH',b'BHR2',2,7,36,123,req,5,100,0,0)
                return data+struct.pack('<I',zlib.crc32(data)),self.peer
        sock=Sock()
        with mock.patch.object(module.socket,'socket',return_value=sock),mock.patch.object(module.time,'perf_counter',c),mock.patch.object(module.secrets,'randbits',return_value=7):
            client=module.Client('private-peer',123,input_source=lambda:bytes.fromhex('000000000880000880'));frame=client.poll()
        return sock,frame
    def test_packets_identical_and_socket_budget_only_changed(self):
        a,fa=self.run_client(original,.002);b,fb=self.run_client(candidate,.002)
        self.assertEqual(a.data,b.data);self.assertEqual(fa,fb);self.assertEqual(a.budget,.06);self.assertEqual(b.budget,.012)
    def test_timeout_still_returns_none(self):
        s,f=self.run_client(candidate,.012,True);self.assertIsNone(f)
    def test_original_late_return_semantics_preserved(self):
        s,f=self.run_client(candidate,.013);self.assertIsNotNone(f)
        self.assertGreater(f['rtt_ms'],12)
if __name__=='__main__':unittest.main()
