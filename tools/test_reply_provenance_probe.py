import json,struct,unittest
from reply_provenance_probe import ReplyTracker,ProvenanceSocket
from test_short_wait_transport import packet,Clock

PEER=('127.0.0.1',49724)
def query(request):return struct.pack('<4sIQI',b'BHP2',request,1,0xffffffff)

class Provenance(unittest.TestCase):
    def test_current_reply_matches_original_send(self):
        t=ReplyTracker(1,PEER);t.sent(query(1),PEER,0.,.001);t.received(packet(1),PEER,.006)
        r=t.snapshot()['worst_reply_age_context']['event'];self.assertAlmostEqual(r['reply_age_seconds'],.005)
        self.assertTrue(r['belongs_to_current_request']);self.assertEqual(t.tracked_replies,1)

    def test_stale_reply_records_its_original_request_age(self):
        t=ReplyTracker(1,PEER);t.sent(query(1),PEER,0.,0.);t.sent(query(2),PEER,.016,.016)
        t.received(packet(1),PEER,.060);r=t.snapshot()['late'][0]
        self.assertAlmostEqual(r['reply_age_seconds'],.060);self.assertFalse(r['belongs_to_current_request'])
        self.assertEqual(t.stale_tracked,1);self.assertEqual(t.late_tracked,1)

    def test_host_and_board_intervals_are_separate(self):
        t=ReplyTracker(1,PEER);t.sent(query(1),PEER,1.,1.);t.sent(query(2),PEER,1.02,1.02)
        t.received(packet(1,[(0,1000000)]),PEER,1.1);t.received(packet(2,[(1,1020000)]),PEER,1.101)
        r=t.snapshot()['recent'][-1]
        self.assertAlmostEqual(r['send_interval_from_previous_reply_request_seconds'],.02)
        self.assertAlmostEqual(r['host_receive_interval_seconds'],.001);self.assertEqual(r['board_source_interval_us'],20000)

    def test_foreign_or_invalid_response_not_used_for_correlation(self):
        t=ReplyTracker(1,PEER);t.sent(query(1),PEER,0.,0.)
        t.received(packet(1),('127.0.0.2',49724),.01)
        bad=bytearray(packet(1));bad[-1]^=1;t.received(bytes(bad),PEER,.01)
        t.received(packet(1,session=2),PEER,.01)
        self.assertEqual(t.foreign_replies,1);self.assertEqual(t.invalid_replies,2);self.assertEqual(t.tracked_replies,0)

    def test_bounded_history_and_unknown_age_are_not_claimed_as_loss(self):
        t=ReplyTracker(1,PEER,history_limit=2)
        for n in (1,2,3):t.sent(query(n),PEER,n,n)
        t.received(packet(1),PEER,4.)
        self.assertEqual(t.history_evictions,1);self.assertEqual(t.untracked_replies,1)
        self.assertIsNone(t.snapshot()['worst_reply_age_context'])

    def test_worst_context_survives_later_small_replies_and_exports_no_secrets(self):
        t=ReplyTracker(1,PEER);t.sent(query(1),PEER,0.,0.);t.received(packet(1),PEER,.1);first=t.snapshot()['worst_reply_age_context']
        for n in range(2,200):t.sent(query(n),PEER,n,n);t.received(packet(n),PEER,n+.001)
        s=t.snapshot();self.assertEqual(s['worst_reply_age_context'],first);self.assertEqual(len(s['recent']),64)
        self.assertLessEqual(len(s['late']),32)
        encoded=json.dumps(s);self.assertNotIn('127.0.0.1',encoded);self.assertNotIn('"session"',encoded)

    def test_socket_forwards_original_packet_and_peer(self):
        clock=Clock();sent=[]
        class Socket:
            def sendto(self,data,peer):sent.append((data,peer));return len(data)
            def recvfrom(self,size):return packet(1),PEER
        t=ReplyTracker(1,PEER);s=ProvenanceSocket(Socket(),t,clock)
        data=query(1);self.assertEqual(s.sendto(data,PEER),len(data));self.assertEqual(sent,[(data,PEER)])
        self.assertEqual(s.recvfrom(512),(packet(1),PEER));self.assertEqual(t.tracked_replies,1)

    def test_observer_failure_does_not_change_forwarding(self):
        clock=Clock();t=ReplyTracker(1,PEER)
        def fail(*args):raise ValueError('observer only')
        t.received=fail
        class Socket:
            def recvfrom(self,size):return b'unchanged',PEER
        s=ProvenanceSocket(Socket(),t,clock);self.assertEqual(s.recvfrom(512),(b'unchanged',PEER))
        self.assertEqual(t.internal_errors,1)

if __name__=='__main__':unittest.main()
