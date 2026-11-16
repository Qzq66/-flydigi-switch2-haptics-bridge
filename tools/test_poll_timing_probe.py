import json,unittest
from poll_timing_probe import DetailedClient

class Clock:
    def __init__(self):self.now=0.
    def __call__(self):return self.now

class Socket:
    def __init__(self,clock):self.clock=clock;self.timeout=False;self.sent=[]
    def sendto(self,*args,**kwargs):self.clock.now+=.002;self.sent.append((args,kwargs));return 6
    def recvfrom(self,*args,**kwargs):
        self.clock.now+=.060 if self.timeout else .010
        if self.timeout:raise TimeoutError('timeout')
        return b'secret-packet',('private-address',49724)

class Client:
    def __init__(self,clock):
        self.clock=clock;self.sock=Socket(clock);self.input_source=self.read;self.terminal_ack_replied=False
    def read(self):self.clock.now+=.004;return b'123456789'
    def poll(self,final_ack=False):
        self.input_source();self.sock.sendto(b'secret-query',('private-address',49724))
        try:self.sock.recvfrom(512)
        except TimeoutError:return None
        self.terminal_ack_replied=final_ack
        return dict(received_at=self.clock(),boot=7,source_us=round(self.clock()*1e6),flags=25 if final_ack else 7,events=[],rtt_ms=10.)

class Probe(unittest.TestCase):
    def test_input_send_receive_durations_and_idle_are_separated(self):
        clock=Clock();raw=Client(clock);client=DetailedClient(raw,clock);client.poll()
        clock.now+=.03;client.poll();s=client.snapshot();last=s['detailed_recent'][-1]
        for key,value in dict(input=.004,send=.002,receive=.010).items():self.assertAlmostEqual(last['stage_seconds'][key],value)
        self.assertAlmostEqual(last['between_polls'],.03);self.assertAlmostEqual(last['unattributed_seconds'],0.)

    def test_timeout_is_retained_after_later_successes(self):
        clock=Clock();raw=Client(clock);client=DetailedClient(raw,clock);client.poll();raw.sock.sock.timeout=True
        self.assertIsNone(client.poll());raw.sock.sock.timeout=False
        for _ in range(100):client.poll()
        snapshot=client.snapshot()
        self.assertTrue(any(i['outcome']=='timeout' for i in snapshot['timing_incidents']))
        self.assertFalse(any(i['outcome']=='timeout' for i in snapshot['detailed_recent']))

    def test_observation_does_not_change_packet_arguments_or_expose_payload(self):
        clock=Clock();raw=Client(clock);sock=raw.sock;client=DetailedClient(raw,clock);client.poll()
        self.assertEqual(sock.sent,[((b'secret-query',('private-address',49724)),{})])
        snapshot=json.dumps(client.snapshot())
        self.assertNotIn('secret-query',snapshot);self.assertNotIn('secret-packet',snapshot);self.assertNotIn('private-address',snapshot)

    def test_input_failure_is_propagated_without_retry(self):
        clock=Clock();raw=Client(clock)
        def fail():raise RuntimeError('disconnected')
        raw.input_source=fail;client=DetailedClient(raw,clock)
        with self.assertRaises(RuntimeError):client.poll()
        s=client.snapshot();self.assertEqual(s['poll_calls'],1)
        self.assertEqual(s['detailed_recent'][-1]['stage_calls']['input'],1)
        self.assertEqual(s['detailed_recent'][-1]['outcome'],'error')

    def test_incident_and_operation_retention_are_bounded(self):
        clock=Clock();raw=Client(clock);client=DetailedClient(raw,clock);raw.sock.sock.timeout=True
        for _ in range(100):client.poll()
        s=client.snapshot();self.assertEqual(len(s['timing_incidents']),32);self.assertEqual(len(s['detailed_recent']),64)

    def test_end_handshake_keeps_accepted_bounded_retry_contract(self):
        clock=Clock();raw=Client(clock);client=DetailedClient(raw,clock)
        self.assertEqual(client.confirm_end()['flags'],25);self.assertTrue(client.terminal_ack_replied)
        self.assertEqual(client.calls,1)

if __name__=='__main__':unittest.main()
