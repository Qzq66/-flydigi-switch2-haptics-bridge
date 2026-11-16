import unittest
from profile_archived_workload import packets,profile,stats
from bridge_protocol import unpack,BridgeFault
class Tests(unittest.TestCase):
    def events(self,n=20):return [dict(at_us=i*1000,sequence=i,motors='0001404000014040',flags=7) for i in range(n)]
    def test_bounded_synthetic_packets_keep_real_payload(self):
        e=self.events();p=packets(e);frames=[unpack(x,1,42) for x in p];self.assertEqual(len(p),3);self.assertEqual([x['motors'].hex() for f in frames for x in f['events']],[x['motors'] for x in e]);self.assertTrue(all(len(f['events'])<=8 for f in frames))
    def test_changed_crc_rejected(self):
        p=bytearray(packets(self.events(1))[0]);p[-1]^=1
        with self.assertRaises(BridgeFault):unpack(p,1,42)
    def test_flag_change_starts_new_packet(self):
        e=self.events(2);e[0]['flags']=3;self.assertEqual(len(packets(e)),2)
    def test_small_profile_is_silent_and_declares_scope(self):
        r=profile(self.events(2),rounds=1);self.assertEqual(r['source_events'],2);self.assertEqual(r['sum_of_eight_feed_calls']['samples'],0);self.assertIn('synthetic',r['scope'])
    def test_no_measurements_not_false_zero_latency(self):self.assertIsNone(stats([])['max_us'])
if __name__=='__main__':unittest.main()
