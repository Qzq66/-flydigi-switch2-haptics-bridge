import ctypes as C,unittest
from config_read_trace import ReadOnlyTrace,compare_bytes,assess_reads
class Lib:
    def __init__(self):self.writes=0
    def hid_write(self,h,b,n):self.writes+=1;return n
    def hid_read_timeout(self,h,b,n,t):C.memmove(b,b'abc',3);return 3
class Tests(unittest.TestCase):
    def test_raw_reply_captured(self):
        t=ReadOnlyTrace(Lib());b=C.create_string_buffer(512);self.assertEqual(t.hid_read_timeout(1,b,512,100),3);self.assertEqual(t.events[0]['raw_hex'],'616263')
    def test_allowed_query_recorded(self):
        t=ReadOnlyTrace(Lib());raw=bytes((0,0x5a,0xa5,0xa1))+bytes(29);self.assertEqual(t.hid_write(1,C.create_string_buffer(raw),33),33);self.assertEqual(t.events[0]['raw_hex'],raw.hex())
    def test_modes_and_stream_forbidden(self):
        for op in (0x53,0x57):
            t=ReadOnlyTrace(Lib());raw=bytes((0,0x5a,0xa5,op))+bytes(29)
            with self.assertRaises(ValueError):t.hid_write(1,C.create_string_buffer(raw),33)
            self.assertEqual(t.lib.writes,0)
    def test_ram_writes_forbidden(self):
        t=ReadOnlyTrace(Lib());raw=bytes((0,0x5a,0xa5,0xa3,4,2,6))+bytes(26)
        with self.assertRaises(ValueError):t.hid_write(1,C.create_string_buffer(raw),33)
        self.assertEqual(t.lib.writes,0)
    def test_capacity_refused_before_query(self):
        t=ReadOnlyTrace(Lib(),max_bytes=1)
        with self.assertRaises(ValueError):t.hid_write(1,C.create_string_buffer(33),33)
        self.assertEqual(t.lib.writes,0)
    def test_mismatch_offsets_and_length(self):self.assertEqual(compare_bytes(b'abc',b'axcd')['different_offsets'],[1,3])
    def test_first_mismatch_never_hidden(self):
        a=assess_reads([dict(comparisons=dict(motors=compare_bytes(b'a',b'b'))),dict(comparisons=dict(motors=compare_bytes(b'a',b'a')))])
        self.assertFalse(a['first_sample_matches']);self.assertFalse(a['all_samples_match']);self.assertEqual(a['mismatching_samples'],[0])
    def test_no_samples_rejected(self):
        with self.assertRaises(ValueError):assess_reads([])
if __name__=='__main__':unittest.main()
