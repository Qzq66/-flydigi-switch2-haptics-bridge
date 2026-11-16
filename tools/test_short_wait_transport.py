import socket,struct,zlib,unittest
from unittest.mock import patch
from short_wait_transport import ShortWaitClient,BridgeFault

class Clock:
    def __init__(self):self.now=0.
    def __call__(self):return self.now

def packet(request,events=(),flags=7,boot=7,session=1):
    stamp=max([at for seq,at in events]+[1000])
    body=struct.pack('<4sBBHQIIIHH',b'BHR2',2,flags,36+len(events)*16,session,request,boot,stamp,len(events),0)
    for seq,at in events:body+=struct.pack('<II8s',at,seq,b'12345678')
    return body+struct.pack('<I',zlib.crc32(body))

class Socket:
    def __init__(self,clock):self.clock=clock;self.timeout=.06;self.timeouts=[];self.sent=[];self.steps=[]
    def bind(self,address):pass
    def settimeout(self,n):self.timeout=n;self.timeouts.append(n)
    def sendto(self,data,peer):self.sent.append(data)
    def recvfrom(self,n):
        if not self.steps:self.clock.now+=self.timeout;raise socket.timeout()
        delay,data,peer=self.steps.pop(0);self.clock.now+=delay
        return data,peer
    def close(self):pass

class ShortWait(unittest.TestCase):
    def make(self):
        clock=Clock();sock=Socket(clock)
        with patch('bridge_transport.socket.socket',return_value=sock):client=ShortWaitClient('127.0.0.1',1,input_source=lambda:b'123456789')
        client.clock=clock;client.request=0
        return client,sock,clock

    def test_wire_input_payload_and_ack_are_unchanged(self):
        client,sock,clock=self.make();sock.steps=[(.001,packet(1,[(0,100)]),('127.0.0.1',49724))]
        self.assertEqual(client.poll()['events'][0]['sequence'],0)
        query=sock.sent[0];self.assertEqual(query[:4],b'BHI2');self.assertEqual(len(query),36)
        self.assertEqual(struct.unpack_from('<I',query,16)[0],0xffffffff);self.assertEqual(query[24:33],b'123456789')
        client.poll();self.assertEqual(struct.unpack_from('<I',sock.sent[1],16)[0],0)

    def test_stale_packets_do_not_restart_total_receive_budget(self):
        client,sock,clock=self.make();sock.steps=[(.004,packet(0),('127.0.0.1',49724)),(.004,packet(0),('127.0.0.1',49724))]
        self.assertIsNone(client.poll());self.assertAlmostEqual(clock.now,.012)
        self.assertAlmostEqual(sock.timeouts[-1],.004);self.assertEqual(client.stale_replies,2)

    def test_late_reply_does_not_advance_ack_and_next_request_recovers_event(self):
        client,sock,clock=self.make();sock.steps=[(.020,packet(1,[(0,100)]),('127.0.0.1',49724))]
        self.assertIsNone(client.poll());self.assertEqual(client.ack,0xffffffff);self.assertEqual(client.late_matching_replies,1)
        sock.steps=[(.001,packet(1,[(0,100)]),('127.0.0.1',49724)),(.001,packet(2,[(0,100)]),('127.0.0.1',49724))]
        self.assertEqual(client.poll()['events'][0]['sequence'],0);self.assertEqual(client.received,1)

    def test_duplicates_are_filtered_but_sequence_gaps_fail(self):
        client,sock,clock=self.make();sock.steps=[(.001,packet(1,[(0,100),(1,200)]),('127.0.0.1',49724))]
        client.poll();sock.steps=[(.001,packet(2,[(1,200),(2,300)]),('127.0.0.1',49724))]
        self.assertEqual([e['sequence'] for e in client.poll()['events']],[2]);self.assertEqual(client.duplicates,1)
        sock.steps=[(.001,packet(3,[(4,400)]),('127.0.0.1',49724))]
        with self.assertRaisesRegex(BridgeFault,'sequence gap'):client.poll()

    def test_crc_and_board_restart_still_fail(self):
        client,sock,clock=self.make();bad=bytearray(packet(1));bad[-1]^=1
        sock.steps=[(.001,bytes(bad),('127.0.0.1',49724))]
        with self.assertRaisesRegex(BridgeFault,'CRC'):client.poll()
        sock.steps=[(.001,packet(2),('127.0.0.1',49724))];client.poll()
        sock.steps=[(.001,packet(3,boot=8),('127.0.0.1',49724))]
        with self.assertRaisesRegex(BridgeFault,'restarted'):client.poll()

    def test_final_ack_requires_terminal_and_keeps_three_attempt_limit(self):
        client,sock,clock=self.make()
        with self.assertRaises(BridgeFault):client.poll(final_ack=True)
        client.terminal_received=True;self.assertIsNone(client.confirm_end())
        self.assertEqual(len(sock.sent),3);self.assertTrue(all(data[:4]==b'BHE2' for data in sock.sent))
        self.assertAlmostEqual(clock.now,.036)

    def test_foreign_peer_is_skipped_and_remaining_budget_shrinks(self):
        client,sock,clock=self.make();sock.steps=[(.005,packet(1),('127.0.0.2',49724)),(.001,packet(1),('127.0.0.1',49724))]
        self.assertIsNotNone(client.poll());self.assertAlmostEqual(sock.timeouts[-1],.007)

    def test_terminal_confirmation_success_and_no_stream_resume(self):
        client,sock,clock=self.make();sock.steps=[(.001,packet(1,flags=25),('127.0.0.1',49724))]
        client.poll();sock.steps=[(.001,packet(2,flags=25),('127.0.0.1',49724))]
        self.assertIsNotNone(client.confirm_end());self.assertTrue(client.terminal_ack_replied)
        sock.steps=[(.001,packet(3),('127.0.0.1',49724))]
        with self.assertRaisesRegex(BridgeFault,'resumed'):client.poll()

if __name__=='__main__':unittest.main()
