import hashlib,tempfile,pathlib,json,unittest
from packet_clock_probe import PacketClockProbe,PacketClockSocket

class FakeSocket:
    def sendto(self,data,peer):self.sent=(data,peer);return len(data)
    def recvfrom(self,size):return b'reply',('peer',1)

class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.t=1.
        def clock():self.t+=.00001;return self.t
        self.p=PacketClockProbe(lambda:round(self.t*1e9),clock=clock,limit=2)
    def test_transparent_send_receive(self):
        raw=FakeSocket();s=PacketClockSocket(raw,self.p)
        self.assertEqual(s.sendto(b'query',('peer',1)),5)
        self.assertEqual(raw.sent,(b'query',('peer',1)))
        self.assertEqual(s.recvfrom(512),(b'reply',('peer',1)))
        self.assertEqual([x['direction'] for x in self.p.rows],['send','receive'])
        self.assertEqual(self.p.rows[1]['sha256'],hashlib.sha256(b'reply').hexdigest())
        self.assertNotIn('payload',self.p.rows[1])
    def test_bound_does_not_block_socket(self):
        s=PacketClockSocket(FakeSocket(),self.p)
        for _ in range(3):self.assertEqual(s.sendto(b'x',('peer',1)),1)
        self.assertEqual(len(self.p.rows),2);self.assertEqual(self.p.overflow,1)
    def test_original_exception_is_preserved(self):
        class Broken:
            def recvfrom(self,size):raise TimeoutError('original')
        with self.assertRaisesRegex(TimeoutError,'original'):PacketClockSocket(Broken(),self.p).recvfrom(512)
        self.assertEqual(self.p.rows,[])
    def test_private_trace_exclusive_and_hash(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d)/'trace.json';summary=self.p.finish(p)
            self.assertEqual(summary['private_trace_sha256'],hashlib.sha256(p.read_bytes()).hexdigest())
            self.assertEqual(len(json.loads(p.read_text())['anchors']),2)
            with self.assertRaises(FileExistsError):self.p.finish(p)

if __name__=='__main__':unittest.main()
