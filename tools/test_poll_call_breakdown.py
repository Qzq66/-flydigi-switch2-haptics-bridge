import json,unittest
from poll_call_breakdown import PollBreakdown,TimedSocket,BreakdownClient
class Clock:
    now=0.
    def __call__(self):return self.now
class Tests(unittest.TestCase):
    def test_call_durations_and_identity(self):
        c=Clock();v=b'input';p=PollBreakdown(lambda:v,c);p.begin();self.assertIs(p.read_input(),v)
        def call():c.now+=.060;return v
        self.assertIs(p.invoke('recvfrom',call),v);p.finish(frame=dict(received_at=c(),source_us=1,flags=7))
        r=p.snapshot()['recent'][0];self.assertAlmostEqual(r['calls'][1]['duration_seconds'],.060);self.assertEqual(r['duration_seconds'],.060)
    def test_exception_original_identity_and_no_private_message(self):
        c=Clock();p=PollBreakdown(lambda:None,c);p.begin();e=OSError('private-address')
        def bad():raise e
        with self.assertRaises(OSError) as caught:p.invoke('recvfrom',bad)
        self.assertIs(caught.exception,e);p.finish(error='OSError');self.assertNotIn('private-address',json.dumps(p.snapshot()));self.assertFalse(p.snapshot()['healthy'])
    def test_call_budget_before_underlying(self):
        p=PollBreakdown(lambda:None,Clock());p.begin()
        for i in range(8):p.invoke('recvfrom',lambda:None)
        with self.assertRaises(ValueError):p.invoke('recvfrom',lambda:self.fail('extra underlying call'))
    def test_poll_budget_before_underlying(self):
        p=PollBreakdown(lambda:None,Clock());p.polls=p.POLLS
        with self.assertRaises(ValueError):p.begin()
    def test_socket_preserves_exact_bytes_and_peer(self):
        class Sock:
            def sendto(self,data,peer):self.got=(data,peer);return len(data)
            def recvfrom(self,n):return (b'unchanged','private-peer')
        p=PollBreakdown(lambda:None,Clock());p.begin();s=Sock();w=TimedSocket(s,p);v=b'original';peer=object();self.assertEqual(w.sendto(v,peer),len(v));self.assertIs(s.got[0],v);self.assertIs(s.got[1],peer);self.assertEqual(w.recvfrom(512),(b'unchanged','private-peer'));p.finish();self.assertNotIn('private-peer',json.dumps(p.snapshot()))
    def test_bounded_maximum_survives_ring(self):
        c=Clock();p=PollBreakdown(lambda:None,c)
        for i in range(200):
            p.begin();c.now+=.9 if i==1 else .001;p.finish(frame=dict(received_at=c(),source_us=i,flags=7))
        d=p.snapshot();self.assertEqual(len(d['recent']),64);self.assertEqual(len(d['slowest']),16);self.assertEqual(d['maximum_receive_gap']['row']['poll_index'],2);self.assertLess(len(json.dumps(d).encode()),262144)
    def test_confirm_end_same_three_attempts(self):
        class Client:
            sock=object()
            def __init__(self):self.args=[]
            def poll(self,**kw):self.args.append(kw);return None
        c=Client();p=PollBreakdown(lambda:None,Clock());w=BreakdownClient(c,p);self.assertIsNone(w.confirm_end());self.assertEqual(c.args,[dict(final_ack=True)]*3)
    def test_source_clock_reversal_rejected(self):
        c=Clock();p=PollBreakdown(lambda:None,c);p.begin()
        def bad():c.now=-1
        with self.assertRaises(ValueError):p.invoke('input_read',bad)
    def test_snapshot_mutation_does_not_change_producer(self):
        p=PollBreakdown(lambda:None,Clock());p.begin();p.finish();d=p.snapshot();d['recent'][0]['start']=-5;self.assertEqual(p.snapshot()['recent'][0]['start'],0)

    def test_original_transport_with_fake_socket_and_clock(self):
        import pathlib,sys,struct,zlib
        from unittest import mock
        sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'handoff/2026-10-22/work'))
        import bridge_transport as original
        c=Clock();c.now=0.
        def source():c.now+=.001;return bytes.fromhex('000000000880000880')
        p=PollBreakdown(source,c)
        class Sock:
            def bind(self,*a):pass
            def settimeout(self,n):self.timeout=n
            def sendto(self,data,peer):self.data=data;self.peer=peer;c.now+=.002;return len(data)
            def recvfrom(self,n):
                c.now+=.003
                req=struct.unpack_from('<I',self.data,4)[0]
                data=struct.pack('<4sBBHQIIIHH',b'BHR2',2,7,36,123,req,5,100,0,0)
                return data+struct.pack('<I',zlib.crc32(data)),self.peer
        sock=Sock()
        with mock.patch.object(original.socket,'socket',return_value=sock),mock.patch.object(original.time,'perf_counter',c):
            base=original.Client('private-peer',123,input_source=p.read_input)
            w=BreakdownClient(base,p);frame=w.poll()
        self.assertEqual(sock.timeout,.06);self.assertEqual(frame['flags'],7);self.assertEqual(sock.data[24:33],bytes.fromhex('000000000880000880'))
        row=p.snapshot()['recent'][0];self.assertEqual([x['kind'] for x in row['calls']],['input_read','sendto','recvfrom'])
        for x,expected in zip(row['calls'],(.001,.002,.003)):self.assertAlmostEqual(x['duration_seconds'],expected)
    def test_final_validation_rejects_corrupt_call(self):
        from poll_call_breakdown_validation import assess_breakdown
        p=PollBreakdown(lambda:None,Clock());p.begin();p.invoke('input_read',lambda:None);p.finish()
        child=dict(poll_call_breakdown=p.snapshot(),transport_diagnostics=dict(poll_calls=1))
        self.assertTrue(assess_breakdown(child)['passed'])
        child['poll_call_breakdown']['recent'][0]['calls'][0]['duration_seconds']=-1
        self.assertFalse(assess_breakdown(child)['passed'])

if __name__=='__main__':unittest.main()
