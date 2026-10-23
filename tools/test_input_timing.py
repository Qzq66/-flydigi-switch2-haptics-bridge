import unittest
from input_timing import view

class Timing(unittest.TestCase):
    def test_waits_for_actual_ready_not_usb_plug_time(self):
        for data in ({},{'phase':'DISCOVERING'},{'phase':'INPUT_READY','started_at_pc_clock':100},{'phase':'INPUT_READY','clock':'monotonic','started_at_monotonic':float('nan')},{'phase':'INPUT_READY','clock':'monotonic','started_at_monotonic':True}):
            self.assertEqual(view(data,150)[0],'WAITING')
        self.assertEqual(view({'phase':'INPUT_READY','clock':'monotonic','started_at_monotonic':200},150)[0],'WAITING')
    def test_prompt_boundaries_and_release(self):
        data=dict(phase='INPUT_READY',clock='monotonic',started_at_monotonic=1000)
        for elapsed,expected in ((0,'EARLY_COUNTDOWN'),(29.99,'EARLY_COUNTDOWN'),(30,'EARLY_PRESS'),(35,'LATE_COUNTDOWN'),(104.99,'LATE_COUNTDOWN'),(105,'LATE_PRESS'),(109.99,'LATE_PRESS'),(110,'RELEASE'),(119.99,'RELEASE'),(120,'ENDED')):
            with self.subTest(elapsed=elapsed):self.assertEqual(view(data,1000+elapsed)[0],expected)
    def test_early_end_cancels_cues(self):self.assertEqual(view(dict(phase='ENDED',started_at_pc_clock=1000),1105),('ENDED',0))

if __name__=='__main__':unittest.main()
