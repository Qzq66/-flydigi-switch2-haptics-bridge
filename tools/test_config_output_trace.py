import ctypes as C,types,unittest
from config_output_trace import VolatileOutputTrace
from test_config_read_trace import Lib
from run_config_stop_trace import short_pulse

def packet(op,payload):
    r=bytearray(33);r[:5]=bytes((0,0x5a,0xa5,op,len(payload)+2));r[5:5+len(payload)]=payload;r[32]=sum(r[3:32])&255;return bytes(r)
class Tests(unittest.TestCase):
    def test_only_known_modes_allowed(self):
        for payload in (bytes.fromhex('0112024000'),bytes.fromhex('011200')):
            t=VolatileOutputTrace(Lib());p=packet(0x53,payload);self.assertEqual(t.hid_write(1,C.create_string_buffer(p),33),33)
    def test_other_mode_rejected(self):
        t=VolatileOutputTrace(Lib());p=packet(0x53,b'bad')
        with self.assertRaises(ValueError):t.hid_write(1,C.create_string_buffer(p),33)
        self.assertEqual(t.lib.writes,0)
    def test_bounded_waveform_only(self):
        for value in (119,137):
            t=VolatileOutputTrace(Lib());p=packet(0x57,bytes((0x98,))+bytes((128,value,value))*8);self.assertEqual(t.hid_write(1,C.create_string_buffer(p),33),33)
        t=VolatileOutputTrace(Lib());p=packet(0x57,bytes((0x98,))+bytes((128,138,128))*8)
        with self.assertRaises(ValueError):t.hid_write(1,C.create_string_buffer(p),33)
    def test_config_writes_still_rejected(self):
        t=VolatileOutputTrace(Lib());p=packet(0xa3,bytes((2,6)))
        with self.assertRaises(ValueError):t.hid_write(1,C.create_string_buffer(p),33)
    def test_normal_pulse_fifteen_frames_then_stop(self):
        now=[0.];frames=[];stops=[];r=types.SimpleNamespace(mode=lambda p:None,stream=frames.append);safe=types.SimpleNamespace(waveform=lambda l,r,**k:(l,r))
        n=short_pulse(r,safe,lambda:stops.append(1),clock=lambda:now[0],pause=lambda n:now.__setitem__(0,now[0]+n))
        self.assertEqual(n,15);self.assertEqual(len(stops),1);self.assertAlmostEqual(now[0],.120);self.assertLessEqual(max(abs(v-128) for pair in frames for side in pair for v in side),9)
    def test_write_failure_still_stops(self):
        stops=[]
        def fail(p):raise OSError('injected transport failure')
        r=types.SimpleNamespace(mode=lambda p:None,stream=fail);safe=types.SimpleNamespace(waveform=lambda *a,**k:b'')
        with self.assertRaises(OSError):short_pulse(r,safe,lambda:stops.append(1))
        self.assertEqual(stops,[1])
    def test_enable_failure_still_stops(self):
        stops=[]
        def fail(p):raise OSError('injected enable failure')
        r=types.SimpleNamespace(mode=fail)
        with self.assertRaises(OSError):short_pulse(r,None,lambda:stops.append(1))
        self.assertEqual(stops,[1])
    def test_late_schedule_stops_without_catchup(self):
        now=[0.];stops=[];frames=[];r=types.SimpleNamespace(mode=lambda p:None,stream=frames.append);safe=types.SimpleNamespace(waveform=lambda *a,**k:b'')
        with self.assertRaises(RuntimeError):short_pulse(r,safe,lambda:stops.append(1),clock=lambda:now[0],pause=lambda n:now.__setitem__(0,now[0]+n+.01))
        self.assertEqual(len(frames),1);self.assertEqual(stops,[1])
if __name__=='__main__':unittest.main()
