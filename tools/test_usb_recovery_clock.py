import unittest
from usb_recovery_clock import RecoveryGate

class RecoveryTests(unittest.TestCase):
    def test_discovery_timeout_is_not_recovery_time(self):
        g=RecoveryGate(1000.)
        self.assertFalse(g.observe(1120.)['recovery_time_reached'])
        self.assertEqual(g.observe(1150.)['remaining_seconds'],40.)
    def test_boundary(self):
        g=RecoveryGate(0.)
        self.assertFalse(g.observe(189.999)['recovery_time_reached'])
        self.assertTrue(g.observe(190.)['recovery_time_reached'])
    def test_reverse_or_nonfinite_clock_rejected(self):
        g=RecoveryGate(1.);g.observe(2.)
        with self.assertRaises(ValueError):g.observe(1.5)
        with self.assertRaises(ValueError):g.observe(float('nan'))
    def test_shortened_wait_rejected(self):
        with self.assertRaises(ValueError):RecoveryGate(0.,120)

if __name__=='__main__':unittest.main()
