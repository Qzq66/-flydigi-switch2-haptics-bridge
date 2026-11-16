import unittest
from analyse_recovered52_heartbeat import span,rows_from
class Tests(unittest.TestCase):
    def sample(self):
        a=dict(event_index=1,phase='poll',outcome='frame',received_at=1.,source_us=100,receive_gap_seconds=None)
        pause=dict(event_index=2,phase='pause',start=1.,end=1.004,duration_seconds=.004)
        b=dict(event_index=3,phase='poll',outcome='frame',start=1.004,end=1.081,received_at=1.080,source_us=80100,receive_gap_seconds=.080,duration_seconds=.077)
        return a,b,{2:pause,3:b}
    def test_boundary_not_overrun(self):
        a,b,r=self.sample();self.assertAlmostEqual(span(r,a,b)['heartbeat_excess_seconds'],0)
    def test_overrun(self):
        a,b,r=self.sample();b.update(received_at=1.1,receive_gap_seconds=.1);self.assertAlmostEqual(span(r,a,b)['heartbeat_excess_seconds'],.02)
    def test_missing_rows_explicit(self):
        a,b,r=self.sample();del r[2];self.assertEqual(span(r,a,b)['missing_phase_indices'],[2]);self.assertFalse(span(r,a,b)['complete_phase_span'])
    def test_not_adjacent_rejected(self):
        a,b,r=self.sample();r[2]=dict(event_index=2,phase='poll',outcome='frame')
        with self.assertRaises(ValueError):span(r,a,b)
    def test_wrong_gap_rejected(self):
        a,b,r=self.sample();b['receive_gap_seconds']=.2
        with self.assertRaises(ValueError):span(r,a,b)
    def test_counter_wrap(self):
        a,b,r=self.sample();a['source_us']=0xfffffff0;b['source_us']=0x10;self.assertEqual(span(r,a,b)['source_interval_us'],32)
    def test_conflicting_rows_rejected(self):
        r=dict(event_index=1,start=1.,end=2.,duration_seconds=1.);other=dict(r,end=3.,duration_seconds=2.)
        d=dict(recent_events=[r,other],contexts=[])
        with self.assertRaises(ValueError):rows_from(d)
    def test_bad_duration_rejected(self):
        d=dict(recent_events=[dict(event_index=1,start=1.,end=2.,duration_seconds=2.)],contexts=[])
        with self.assertRaises(ValueError):rows_from(d)
if __name__=='__main__':unittest.main()
