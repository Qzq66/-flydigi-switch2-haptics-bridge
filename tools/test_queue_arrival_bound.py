import unittest
from queue_arrival_bound import bound
class Tests(unittest.TestCase):
    def rows(self):return [dict(event_index=1,phase='poll',start=0.,end=.001,outcome='frame',event_count=8,flags=7),dict(event_index=2,phase='pause',start=.0011,end=.005),dict(event_index=3,phase='poll',start=.0051,end=.006,outcome='frame',event_count=0,flags=7),dict(event_index=4,phase='pause',start=.0061,end=.010),dict(event_index=5,phase='poll',start=.0101,end=.012,outcome='frame',event_count=2,flags=7),dict(event_index=6,phase='pause',start=.0121,end=.016)]
    def test_old_published_frame_not_backlog_candidate(self):
        r=bound(.003,.011,self.rows());self.assertEqual(r['maximum_new_frames'],1);self.assertEqual(r['maximum_new_motor_events'],0);self.assertFalse(r['actual_queue_depth_measured'])
    def test_uncertain_publication_counted_conservatively(self):
        r=bound(.00105,.011,self.rows());self.assertEqual(r['maximum_new_frames'],2);self.assertEqual(r['maximum_new_motor_events'],8)
    def test_missing_phase_refuses_bound(self):
        rows=self.rows();rows.pop(2)
        with self.assertRaises(ValueError):bound(.003,.011,rows)
    def test_complete_marker_not_silently_single_counted(self):
        rows=self.rows();rows[2]['flags']=25
        with self.assertRaises(ValueError):bound(.003,.011,rows)
if __name__=='__main__':unittest.main()
