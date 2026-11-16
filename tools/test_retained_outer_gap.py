import json,unittest
from retained_outer_gap import RetainingProbe,bind_to_fault
class Tests(unittest.TestCase):
    def setUp(self):self.now=0.;self.p=RetainingProbe(lambda:self.now)
    def advance(self,n):self.now+=n
    def test_largest_and_last_are_separate(self):
        self.p.after_tick();self.p.call('sleep_or_wakeup',self.advance,.010);self.p.before_tick();maximum=self.p.maximum_gap
        self.p.after_tick();self.p.call('cancel_stat',self.advance,.006);self.p.before_tick();self.assertIs(self.p.maximum_gap,maximum);self.assertAlmostEqual(self.p.last_gap['seconds'],.006)
    def test_maximum_cannot_impersonate_final_fault(self):
        gap=dict(start=1.,end=1.01);fault=dict(tick_entry=2.006,context=[dict(end=2.),{}]);self.assertFalse(bind_to_fault(gap,fault)['matched'])
    def test_last_gap_matches_clock_window(self):
        self.assertTrue(bind_to_fault(dict(start=2.00001,end=2.005),dict(tick_entry=2.006,context=[dict(end=2.),{}]))['matched'])
    def test_absent_clock_never_guessed(self):self.assertFalse(bind_to_fault({},dict(tick_entry=None,context=[]))['matched'])
    def test_retention_stays_bounded(self):
        for _ in range(2000):self.p.after_tick();self.p.call('input_processing',self.advance,.001);self.p.before_tick()
        self.assertLess(len(json.dumps(self.p.summary())),262144);self.assertEqual(self.p.summary()['retained'],256)
if __name__=='__main__':unittest.main()
