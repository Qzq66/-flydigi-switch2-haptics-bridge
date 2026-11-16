import hashlib,struct,unittest
from analyse_short_ram_path import receive_components,inspect
from test_component_receive_analysis import reply
from test_pktmon_capture import capture,block,option
from test_forensic_wifi_decode import wifi

def trace(values):
    return dict(anchors=[dict(perf_mid=1.,utc_ns=1000000000,bracket_ns=100),dict(perf_mid=2.,utc_ns=2000000000,bracket_ns=100)],
        rows=[dict(direction='receive',sha256=hashlib.sha256(v).hexdigest(),at=1.01+i*.1) for i,v in enumerate(values)])

def wifi_capture(value,ticks):
    frame=wifi(value)
    return (block(0x0a0d0d0a,struct.pack('<IHHq',0x1a2b3c4d,1,0,-1))+
        block(1,struct.pack('<HHI',1,0,65535)+option(9,b'\x09'))+
        block(6,struct.pack('<IIIII',0,0,ticks,len(frame),len(frame))+frame+b'\0'*((-len(frame))%4)))

class ShortAnalysisTests(unittest.TestCase):
    def test_counters_keep_ids_and_do_not_sum_copies_or_drops(self):
        text='7 Driver Lower Rx 3 192 | Tx 3 192\n Upper Rx 3 192 | Tx 3 192\n9 TCPIP Dropped Rx 99 999 | Tx 0 0\n Lower Rx 0 0 | Tx 1 64'
        self.assertEqual(receive_components(text),{7:3})
    def test_counters_parse_thousands(self):
        self.assertEqual(receive_components('12 TCPIP Lower Rx 1,234 99,000 | Tx 3 192'),{12:1234})
    def test_all_three_wifi_and_duplicate_copies(self):
        values=[reply(i) for i in range(3)]
        data=b''.join(wifi_capture(v,1000000000+i*100000000) for i,v in enumerate(values))+wifi_capture(values[0],1000000000)
        r=inspect(data,trace(values));self.assertTrue(r['all_three_observed']);self.assertEqual(r['matched_component_copies'],4)
        self.assertEqual(r['formats'],{'known_plaintext_wifi':4})
    def test_missing_or_foreign_reply_not_complete(self):
        values=[reply(i) for i in range(3)];r=inspect(capture(values[0])+capture(values[1])+capture(reply(99)),trace(values))
        self.assertFalse(r['all_three_observed']);self.assertEqual(r['matched_reply_sequences'],2)

if __name__=='__main__':unittest.main()
