import unittest
from bounded_multi_event_renderer import BoundedMultiEventRenderer,BridgeFault
class Tests(unittest.TestCase):
    def make(self):
        r=BoundedMultiEventRenderer();r.armed=True;r.armed_at=0.;r.output_start=0.;return r
    def block(self,r,active):
        now=0. if r.rendered_until is None else r.rendered_until;r.last_received=now
        r.values=[[.02 if active else 0.,160.,0.,320.] for _ in range(2)]
        return r.block(now)
    def episode(self,r):
        self.block(r,True)
        for _ in range(65):self.block(r,False)
    def test_three_events_and_fourth_rejected(self):
        r=self.make()
        for _ in range(3):self.episode(r)
        self.assertEqual(r.completed_events,3);self.assertEqual(r.lifetime_active,[24,24])
        self.assertIsNone(self.block(r,True));self.assertEqual(r.muted_reason,'three-event session completed')
    def test_early_resume_fault(self):
        r=self.make();self.block(r,True);self.block(r,False)
        with self.assertRaises(BridgeFault):self.block(r,True)
    def test_single_event_320ms_still_limited(self):
        r=self.make()
        for _ in range(40):self.block(r,True)
        with self.assertRaises(BridgeFault):self.block(r,True)
    def test_heartbeat_still_faults(self):
        r=self.make();r.last_received=-.081
        with self.assertRaises(BridgeFault):r.block(0.)
    def test_fault_cannot_be_cleared_by_quiet(self):
        r=self.make();self.block(r,True);self.block(r,False)
        with self.assertRaises(BridgeFault):self.block(r,True)
        with self.assertRaises(BridgeFault):self.block(r,False)
if __name__=='__main__':unittest.main()
