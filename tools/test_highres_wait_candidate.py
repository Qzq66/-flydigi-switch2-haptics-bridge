import types,unittest
from highres_wait_candidate import HighResolutionWait,blocking_request
class FakeAPI:
    def __init__(self,status=0):self.status=status;self.calls=[]
    def create(self):self.calls.append('create');return 123
    def arm(self,h,t):self.calls.append(('arm',h,t));return True
    def wait(self,h,t):self.calls.append(('wait',h,t));return self.status
    def cancel(self,h):self.calls.append('cancel');return True
    def close(self,h):self.calls.append('close');return True
class Tests(unittest.TestCase):
    def test_negative_relative_100ns_units(self):
        a=FakeAPI();t=HighResolutionWait(a);t.sleep(.0002);self.assertIn(('arm',123,-2000),a.calls);t.close()
    def test_timeout_fails_without_fallback(self):
        a=FakeAPI(258);t=HighResolutionWait(a)
        with self.assertRaises(TimeoutError):t.sleep(.001)
        self.assertIn('cancel',a.calls);t.close()
    def test_native_wait_failure_raises(self):
        a=FakeAPI(0xffffffff);t=HighResolutionWait(a)
        with self.assertRaises(OSError):t.sleep(.001)
        t.close()
    def test_creation_failure_no_fallback(self):
        a=FakeAPI();a.create=lambda:None
        with self.assertRaises(OSError):HighResolutionWait(a)
    def test_close_idempotent_no_handle_leak(self):
        a=FakeAPI();t=HighResolutionWait(a);t.close();t.close();self.assertEqual(a.calls.count('close'),1)
    def test_long_or_nonfinite_wait_refused(self):
        a=FakeAPI();t=HighResolutionWait(a)
        for value in (0,-1,.002,float('nan')):
            with self.assertRaises(ValueError):t.sleep(value)
        t.close()
    def test_deadline_request_has_no_busy_guard(self):
        self.assertAlmostEqual(blocking_request(1.,1.0002,True),.0002);self.assertEqual(blocking_request(1.,.9,True),0);self.assertEqual(blocking_request(1.,None,False),.001)
if __name__=='__main__':unittest.main()
