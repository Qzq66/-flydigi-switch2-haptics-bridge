import hashlib,struct,unittest,zlib
from component_receive_analysis import correlate
from test_pktmon_capture import capture

def reply(request=1):
    body=struct.pack('<4sBBHQIIIHH',b'BHR2',2,7,36,123,request,45,100,0,0)
    return body+struct.pack('<I',zlib.crc32(body))

def trace(payload,rows=1):
    return dict(errors=0,overflow=0,anchors=[dict(perf_mid=1.,utc_ns=1000000000,bracket_ns=100),dict(perf_mid=2.,utc_ns=2000000000,bracket_ns=100)],
        rows=[dict(direction='receive',at=1.01,sha256=hashlib.sha256(payload).hexdigest()) for _ in range(rows)])

class CorrelationTests(unittest.TestCase):
    def test_duplicate_component_copies_are_one_receive(self):
        p=reply();r=correlate(trace(p),capture(p)+capture(p,ticks=1001000000))
        self.assertTrue(r['complete_receive_coverage']);self.assertEqual(r['component_copies'],2)
        self.assertEqual(r['matched_receive_rows'],1);self.assertEqual(r['component_to_application_ns']['max'],10000000)
    def test_missing_is_incomplete(self):
        self.assertFalse(correlate(trace(reply()),capture(reply(2)))['complete_receive_coverage'])
    def test_repeated_payload_is_ambiguous(self):
        r=correlate(trace(reply(),2),capture(reply()));self.assertEqual(r['ambiguous_payload_groups'],1)
        self.assertFalse(r['complete_receive_coverage'])
    def test_crc_corruption_is_not_matched(self):
        p=reply()[:-1]+b'X';self.assertEqual(correlate(trace(p),capture(p))['matched_receive_rows'],0)
    def test_drop_or_observer_overflow_rejects_full_coverage(self):
        p=reply();self.assertFalse(correlate(trace(p),capture(p,drops=1))['complete_receive_coverage'])
        t=trace(p);t['overflow']=1
        with self.assertRaises(ValueError):correlate(t,capture(p))
    def test_clock_drift_rejected(self):
        p=reply();t=trace(p);t['anchors'][1]['utc_ns']+=3000000
        with self.assertRaises(ValueError):correlate(t,capture(p))

if __name__=='__main__':unittest.main()
