import struct,unittest
from pcapng_experiment import packets,udp_payload
from capture_clock import anchor,map_to_utc

def block(kind,body,endian='<'):
    size=len(body)+12;return struct.pack(endian+'II',kind,size)+body+struct.pack(endian+'I',size)
def option(code,value,endian='<'):
    return struct.pack(endian+'HH',code,len(value))+value+b'\0'*((-len(value))%4)
def capture(payload=b'CLK1test',endian='<',resolution=9,offset=0,link=1,ticks=1_000_000_000,drops=0):
    shb=block(0x0a0d0d0a,struct.pack(endian+'IHHq',0x1a2b3c4d,1,0,-1),endian)
    opts=option(9,bytes([resolution]),endian)+option(14,struct.pack(endian+'q',offset),endian)
    idb=block(1,struct.pack(endian+'HHI',link,0,65535)+opts,endian)
    udp=struct.pack('!HHHH',40000,49724,len(payload)+8,0)+payload
    ip=struct.pack('!BBHHHBBH4s4s',0x45,0,len(udp)+20,0,0x4000,64,17,0,b'\xc0\xa8\x89\x01',b'\xc0\xa8\x89\xff')+udp
    frame=b'\0'*12+b'\x08\x00'+ip if link==1 else ip
    epb=struct.pack(endian+'IIIII',0,ticks>>32,ticks&0xffffffff,len(frame),len(frame))+frame+b'\0'*((-len(frame))%4)
    epb+=option(2,struct.pack(endian+'I',2),endian)+option(4,struct.pack(endian+'Q',drops),endian)
    return shb+idb+block(6,epb,endian)

class Capture(unittest.TestCase):
    def test_little_and_big_endian_and_interface_direction(self):
        for endian in ('<','>'):
            p=list(packets(capture(endian=endian)))[0]
            self.assertEqual(p['timestamp_ns'],1_000_000_000);self.assertEqual(p['direction'],2)
            self.assertEqual(udp_payload(p),b'CLK1test')
    def test_binary_timestamp_and_signed_offset(self):
        p=list(packets(capture(resolution=0x8a,ticks=1024,offset=-1)))[0]
        self.assertEqual(p['timestamp_ns'],0)
    def test_multiple_sections_do_not_merge_interface_identity(self):
        rows=list(packets(capture()+capture(endian='>')))
        self.assertEqual([(p['section'],p['interface']) for p in rows],[(0,0),(1,0)])
    def test_raw_ipv4_link(self):self.assertEqual(udp_payload(list(packets(capture(link=101)))[0]),b'CLK1test')
    def test_truncated_block_and_bad_trailer_fail(self):
        for data in (capture()[:-1],capture()[:-4]+b'\0'*4):
            with self.assertRaises(ValueError):list(packets(data))
    def test_unknown_link_and_fragment_not_used(self):
        p=list(packets(capture(link=999)))[0]
        with self.assertRaises(ValueError):udp_payload(p)
        p=list(packets(capture(link=101)))[0];raw=bytearray(p['data']);raw[6:8]=b'\x20\x00';p['data']=bytes(raw)
        with self.assertRaises(ValueError):udp_payload(p)
    def test_drop_count_is_retained(self):self.assertEqual(list(packets(capture(drops=4)))[0]['reported_drops'],4)
    def test_no_timestamp_block_is_rejected(self):
        shb=capture()[:28]
        with self.assertRaises(ValueError):list(packets(shb+block(3,b'\0'*4)))
    def test_clock_mapping_and_drift_rejection(self):
        a=[dict(perf_mid=1.,utc_ns=1_000_000_000,bracket_ns=100),dict(perf_mid=2.,utc_ns=2_000_000_000,bracket_ns=100)]
        self.assertEqual(map_to_utc(1.5,a),1_500_000_000)
        a[1]['utc_ns']+=3_000_000
        with self.assertRaises(ValueError):map_to_utc(1.5,a)
    def test_anchor_chooses_small_bracket_without_loading_api(self):
        values=iter([0.,.001,1.,1.000001]);utcs=iter([100,200])
        a=anchor(lambda:next(utcs),lambda:next(values),samples=2)
        self.assertEqual(a['utc_ns'],200);self.assertLess(a['bracket_ns'],2000)

if __name__=='__main__':unittest.main()
