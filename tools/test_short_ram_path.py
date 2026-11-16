import socket,struct,unittest,zlib
from short_ram_path import sram_bounds,three_queries

def block(address=0x20000000,index=0,count=1):
    b=bytearray(512);struct.pack_into('<8I',b,0,0x0a324655,0x9e5d5157,0x2000,address,256,index,count,0)
    struct.pack_into('<I',b,508,0x0ab16f30);return bytes(b)

class Fake:
    def __init__(self,mode='ok'):self.sent=[];self.mode=mode
    def sendto(self,data,peer):self.sent.append((data,peer));return len(data)
    def recvfrom(self,size):
        if self.mode=='timeout':raise socket.timeout('no reply')
        data,peer=self.sent[-1];magic,request,session,ack=struct.unpack('<4sIQI',data)
        count=int(self.mode=='events')
        b=struct.pack('<4sBBHQIIIHH',b'BHR2',2,1,36+16*count,session,request,7,100,count,0)
        if count:b+=struct.pack('<II8s',100,0,b'\0'*8)
        b+=struct.pack('<I',zlib.crc32(b))
        if self.mode=='crc':b=b[:-1]+bytes([b[-1]^1])
        if self.mode=='peer':peer=('foreign',49724)
        return b,peer

class ShortPathTests(unittest.TestCase):
    def test_sram_bounds(self):self.assertEqual(sram_bounds(block())['maximum_end'],'0x20000100')
    def test_flash_target_rejected(self):
        with self.assertRaises(ValueError):sram_bounds(block(0x10000000))
    def test_sram_end_overflow_rejected(self):
        with self.assertRaises(ValueError):sram_bounds(block(0x20081f80))
    def test_empty_and_corrupt_block(self):
        for b in (b'',block()[:-1],b'\0'*512):
            with self.assertRaises(ValueError):sram_bounds(b)
    def test_duplicate_or_incomplete_numbering(self):
        for b in (block(count=2),block(count=2)+block(count=2)):
            with self.assertRaises(ValueError):sram_bounds(b)
    def test_exactly_three_read_queries(self):
        f=Fake();pauses=[];r=three_queries(f,('peer',49724),123,pauses.append)
        self.assertEqual(len(r),3);self.assertEqual(len(f.sent),3);self.assertEqual(pauses,[.25,.25])
        for data,peer in f.sent:self.assertEqual(data[:4],b'BHP2');self.assertEqual(len(data),20)
    def test_timeout_never_retries(self):
        f=Fake('timeout')
        with self.assertRaises(socket.timeout):three_queries(f,('peer',49724),123,lambda n:None)
        self.assertEqual(len(f.sent),1)
    def test_foreign_peer_stops(self):
        f=Fake('peer')
        with self.assertRaises(ValueError):three_queries(f,('peer',49724),123,lambda n:None)
        self.assertEqual(len(f.sent),1)
    def test_bad_crc_stops(self):
        f=Fake('crc')
        with self.assertRaises(Exception):three_queries(f,('peer',49724),123,lambda n:None)
        self.assertEqual(len(f.sent),1)
    def test_upstream_fields_not_expected(self):
        f=Fake('events')
        with self.assertRaisesRegex(ValueError,'upstream'):three_queries(f,('peer',49724),123,lambda n:None)
        self.assertEqual(len(f.sent),1)

if __name__=='__main__':unittest.main()
