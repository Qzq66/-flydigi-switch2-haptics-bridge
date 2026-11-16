import struct,unittest
from registration_input_probe import InputProbe,ObservedSocket,firmware_shape_valid
N=bytes.fromhex('000000000880000880')
def packet(v,n=7):return struct.pack('<4sIQII9s3x',b'BHI2',n,123,0,n,v)
class Tests(unittest.TestCase):
    def test_categories_roundtrip(self):
        for prefix,key in [('000040','L'),('400000','R'),('400040','LR'),('080000','A'),('000000','neutral')]:
            v=bytes.fromhex(prefix)+N[3:];p=InputProbe(lambda:v);self.assertEqual(p(),v);p.sent(packet(v));p.replied(7)
            self.assertEqual(p.snapshot()['categories'][key],dict(reads=1,sends=1,replies=1))
    def test_stale_reply_does_not_confirm(self):
        p=InputProbe(lambda:N);p();p.sent(packet(N));p.replied(6);self.assertEqual(p.replies,0)
    def test_mismatch_latches(self):
        p=InputProbe(lambda:N);p()
        with self.assertRaises(ValueError):p.sent(packet(bytes.fromhex('080000')+N[3:]))
        self.assertTrue(p.failed)
    def test_invalid_shape_rejected(self):
        for v in (b'',b'0'*9,bytes.fromhex('100000')+N[3:],b'\0'*9):self.assertFalse(firmware_shape_valid(v))
    def test_bounds(self):
        for x in (448,3648):self.assertTrue(firmware_shape_valid(N[:3]+bytes((x&255,((x>>8)&15)|((x&15)<<4),x>>4))*2))
    def test_change_storage_bounded(self):
        p=InputProbe(lambda: N if p.reads%2==0 else bytes.fromhex('080000')+N[3:])
        for _ in range(300):p()
        self.assertEqual(len(p.changes),128);self.assertEqual(p.omitted_changes,172)
    def test_capacity_fails_before_read(self):
        p=InputProbe(lambda:self.fail('underlying read'));p.reads=p.LIMIT
        with self.assertRaises(ValueError):p()
    def test_socket_forwards_exact_bytes(self):
        class Socket:
            def sendto(self,data,peer):self.data=data;self.peer=peer;return len(data)
        p=InputProbe(lambda:N);p();sock=Socket();w=ObservedSocket(sock,p);data=packet(N);self.assertEqual(w.sendto(data,'private'),len(data));self.assertIs(sock.data,data)
        self.assertNotIn('private',str(p.snapshot()))
    def test_socket_failure_not_recorded(self):
        class Socket:
            def sendto(self,*a):raise OSError('failed')
        p=InputProbe(lambda:N);p()
        with self.assertRaises(OSError):ObservedSocket(Socket(),p).sendto(packet(N),'x')
        self.assertEqual(p.sends,0)
    def test_terminal_not_counted_as_input(self):
        p=InputProbe(lambda:N);p();p.sent(packet(N));p.sent(b'BHE2'+b'0'*16);p.replied(7);self.assertEqual(p.replies,0)
if __name__=='__main__':unittest.main()
