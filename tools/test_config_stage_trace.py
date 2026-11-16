import types,unittest
from run_config_stage_trace import staged_pulse
class Tests(unittest.TestCase):
    def run_stage(self,fail=None):
        now=[0.];calls=[]
        def capture(label):
            calls.append(label)
            if label==fail:raise OSError('injected read failure')
            return label
        reader=types.SimpleNamespace(mode=lambda p:calls.append('enable'),stream=lambda p:calls.append(p))
        def waveform(*a,**k):return 'off' if k.get('off') else 'wave' if a else 'neutral'
        safe=types.SimpleNamespace(waveform=waveform)
        return now,calls,lambda:staged_pulse(reader,safe,capture,lambda:calls.append('disable'),clock=lambda:now[0],pause=lambda n:now.__setitem__(0,now[0]+n))
    def test_order_and_single_pulse(self):
        now,calls,run=self.run_stage();n,stages=run();self.assertEqual(n,15);self.assertEqual(calls[:2],['enable','enabled_no_stream']);i=calls.index('stream_completed_channels_off');self.assertEqual(calls[i-2:i],['neutral','off']);self.assertEqual(calls[-2:],['disable','runtime_disabled']);self.assertEqual(calls.count('wave'),15);self.assertEqual(calls.count('disable'),1)
    def test_enable_read_failure_stops_without_wave(self):
        now,calls,run=self.run_stage('enabled_no_stream')
        with self.assertRaises(OSError):run()
        self.assertEqual(calls,['enable','enabled_no_stream','disable'])
    def test_postwave_read_failure_still_disables(self):
        now,calls,run=self.run_stage('stream_completed_channels_off')
        with self.assertRaises(OSError):run()
        self.assertEqual(calls[-1],'disable');self.assertEqual(calls.count('wave'),15)
    def test_poststop_read_failure_does_not_reenable(self):
        now,calls,run=self.run_stage('runtime_disabled')
        with self.assertRaises(OSError):run()
        self.assertEqual(calls.count('enable'),1);self.assertEqual(calls.count('disable'),1)
if __name__=='__main__':unittest.main()
