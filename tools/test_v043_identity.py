import unittest
from pico_v043_probe import exact_043

class Identity(unittest.TestCase):
    def test_exact_lab_candidate(self):self.assertTrue(exact_043('Bridge Pro Live 043','BPCAP-RP2350-LOCAL-043',1,4))
    def test_other_devices_and_usages_rejected(self):
        for args in (('Bridge Pro Live 042','BPCAP-RP2350-LOCAL-042',1,4),('APEX6Pro','BPCAP-RP2350-LOCAL-043',1,4),('Bridge Pro Live 043','physical-controller',1,4),('Bridge Pro Live 043','BPCAP-RP2350-LOCAL-043',0xffa0,4),('Bridge Pro Live 043','BPCAP-RP2350-LOCAL-043',1,6)):
            with self.subTest(args=args):self.assertFalse(exact_043(*args))

if __name__=='__main__':unittest.main()
