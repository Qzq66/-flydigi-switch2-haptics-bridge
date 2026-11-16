import unittest
from cross_thread_fault_analysis import compare
class Tests(unittest.TestCase):
    def rows(self):return [dict(event_index=1,phase='pause',start=0.,end=.004),dict(event_index=2,phase='poll',start=.0041,end=.006,outcome='frame',received_at=.0059,event_count=0,flags=7),dict(event_index=3,phase='pause',start=.0061,end=.011)]
    def test_other_thread_progress_and_zero_event_frame(self):
        r=compare(.002,.010,self.rows());self.assertTrue(r['context_contiguous']);self.assertTrue(r['context_brackets_gap']);self.assertTrue(r['collector_progress_observed']);self.assertEqual(len(r['accepted_frames_inside_gap']),1);self.assertEqual(r['new_motor_events_in_accepted_frames'],0)
    def test_partial_poll_not_counted_as_received_frame(self):
        r=compare(.0042,.005,self.rows());self.assertEqual(r['accepted_frames_inside_gap'],[])
    def test_missing_context_explicit(self):
        rows=self.rows();rows.pop(1);self.assertFalse(compare(.002,.010,rows)['context_contiguous'])
    def test_wait_is_not_cpu_claim(self):self.assertIn('not CPU occupancy',compare(.002,.010,self.rows())['limitations'][0])
    def test_invalid_window_rejected(self):
        with self.assertRaises(ValueError):compare(.01,.001,self.rows())
    def test_no_rows_rejected(self):
        with self.assertRaises(ValueError):compare(.02,.03,self.rows())
if __name__=='__main__':unittest.main()
