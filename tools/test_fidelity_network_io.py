"""USB wait isolation and reset phase races with injected I/O, no devices."""
import threading,time,unittest
from fidelity_network_io import CapturedInjector,snapshot_then_reset,SNAPSHOT,wait_full_flash
from test_fidelity_network import Clock
from fidelity_network_session import StreamSession
from test_live_fidelity_candidate import frame

def events(n=3):return [dict(at_us=i*16000,motors='0001404000014040') for i in range(n)]

class NetworkIO(unittest.TestCase):
    def test_source_clock_does_not_accumulate_usb_write_duration(self):
        clock=Clock();sent=[]
        def send(i,raw):sent.append((i,clock()));clock.pause(.006)
        inj=CapturedInjector(events(),.100,send,clock=clock,wait=clock.pause);inj.run();proof=inj.evidence()
        self.assertIsNone(inj.error);self.assertEqual(len(proof['sent_motor_fields']),3)
        for i,at in sent:self.assertAlmostEqual(at,.100+i*.016)
        self.assertTrue(all(abs(n-.006)<1e-9 for n in proof['injection_write_seconds']))
        self.assertTrue(inj.join())

    def test_native_usb_wait_does_not_block_caller_but_requires_join(self):
        entered=threading.Event();release=threading.Event()
        def send(i,raw):entered.set();release.wait(1)
        # Test thread ownership only; OS scheduling is deliberately not evidence.
        inj=CapturedInjector(events(1),0,send,clock=lambda:0.)
        try:
            inj.start();self.assertTrue(entered.wait(1))
            # Service an actual renderer block and confirmed stop while USB waits.
            clock=Clock();sent=[]
            session=StreamSession(lambda:None,lambda l,r:sent.append((l,r)),lambda:dict(runtime_disable_ack=True),clock,clock.pause)
            session.feed(frame(0));session.arm();clock.now=.064;session.feed(frame(clock()));session.tick(clock())
            self.assertEqual(session.frames,1);self.assertEqual(len(sent[0][0]),8);session.stop()
            self.assertTrue(session.summary()['output_stop_confirmed'])
            self.assertFalse(inj.cancel_and_join(.001));self.assertFalse(inj.done.is_set())
        finally:release.set();self.assertTrue(inj.join(1))

    def test_late_injection_aborts_without_catchup(self):
        clock=Clock();sent=[]
        def send(i,raw):sent.append(i);clock.pause(.025)
        inj=CapturedInjector(events(),.1,send,clock=clock,wait=clock.pause);inj.run()
        self.assertEqual(sent,[0]);self.assertIn('late',inj.error)

    def test_cancellation_during_wait_sends_nothing(self):
        clock=Clock();sent=[]
        inj=CapturedInjector(events(),.1,lambda i,r:sent.append(i),clock=clock)
        def wait(n):clock.pause(n);inj.stop_event.set()
        inj.wait=wait;inj.run();self.assertEqual(sent,[]);self.assertTrue(inj.cancelled)

    def test_write_error_and_duration_timeout_are_preserved(self):
        for mode in ('error','timeout'):
            clock=Clock()
            def send(i,raw):
                if mode=='error':raise OSError('HID write failed')
                clock.pause(.081)
            inj=CapturedInjector(events(),0,send,clock=clock,wait=clock.pause);inj.run()
            self.assertTrue(inj.done.is_set());self.assertIsNotNone(inj.error)
            self.assertLessEqual(len(inj.writes),1)

    def test_worker_is_one_shot_and_order_is_bounded(self):
        clock=Clock();inj=CapturedInjector(events(1),0,lambda i,r:None,clock=clock);inj.run()
        with self.assertRaisesRegex(RuntimeError,'one-shot'):inj.run()
        with self.assertRaisesRegex(RuntimeError,'one-shot'):inj.start()
        for source in ([],[dict(at_us=320001,motors='00'*8)],events()+events()):
            with self.assertRaises(ValueError):CapturedInjector(source,0,lambda i,r:None)

    def test_reset_waits_for_exact_snapshot_marker(self):
        clock=Clock();calls=[];replies=iter([None,b'BCAP\5\0\0\1',b'SNAP043\0',SNAPSHOT])
        result=snapshot_then_reset(lambda:next(replies),lambda:calls.append(clock()),clock,clock.pause)
        self.assertEqual(result['snapshot_probe_attempts'],4);self.assertAlmostEqual(calls[0],.15)
        self.assertTrue(result['snapshot_phase_confirmed']);self.assertEqual(len(calls),1)

    def test_snapshot_transition_timeout_retries_but_never_resets_early(self):
        clock=Clock();calls=[];attempt=[0]
        def read():
            attempt[0]+=1
            if attempt[0]<3:raise TimeoutError('ending, not snapshot yet')
            return SNAPSHOT
        result=snapshot_then_reset(read,lambda:calls.append(clock()),clock,clock.pause)
        self.assertEqual(len(calls),1);self.assertEqual(result['snapshot_probe_attempts'],3)

    def test_missing_snapshot_and_reset_write_failure_cannot_pass(self):
        clock=Clock();calls=[]
        with self.assertRaisesRegex(TimeoutError,'not confirmed'):snapshot_then_reset(lambda:None,lambda:calls.append(1),clock,clock.pause,timeout=.1)
        self.assertEqual(calls,[])
        def fail():raise OSError('reset write failed')
        with self.assertRaisesRegex(OSError,'reset write'):snapshot_then_reset(lambda:SNAPSHOT,fail,clock,clock.pause)

    def test_bootsel_delay_keeps_verifying_without_requesting_another_reset(self):
        clock=Clock();calls=[]
        def verify():calls.append(clock());return clock()>=.75
        proof=wait_full_flash(verify,timeout=1,clock=clock,pause=clock.pause)
        self.assertTrue(proof['matched']);self.assertEqual(proof['attempts'],4);self.assertEqual(calls,[0,.25,.5,.75])

    def test_bootsel_immediate_match_does_not_wait_or_reset(self):
        clock=Clock();proof=wait_full_flash(lambda:True,clock=clock,pause=clock.pause)
        self.assertEqual(proof,dict(matched=True,attempts=1,elapsed_seconds=0.))

    def test_bootsel_missing_or_wrong_flash_does_not_pass(self):
        clock=Clock();proof=wait_full_flash(lambda:False,timeout=.3,clock=clock,pause=clock.pause)
        self.assertFalse(proof['matched']);self.assertAlmostEqual(proof['elapsed_seconds'],.3)
        self.assertEqual(proof['attempts'],3)

    def test_bootsel_verify_error_is_not_hidden_as_a_match(self):
        clock=Clock()
        def fail():raise OSError('readback failed')
        with self.assertRaisesRegex(OSError,'readback failed'):wait_full_flash(fail,clock=clock,pause=clock.pause)

if __name__=='__main__':unittest.main()
