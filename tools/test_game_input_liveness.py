import unittest
from game_input_liveness import Liveness,NEUTRAL,RIGHT,LOWER

class InputLiveness(unittest.TestCase):
    def test_neutral_stuck_and_wrong_button_cannot_pass(self):
        for value in (NEUTRAL,RIGHT,LOWER):
            gate=Liveness()
            for t in range(500):self.assertFalse(gate.feed(value,t*.01))

    def test_ordered_buttons_require_release_and_final_quiet(self):
        gate=Liveness()
        for value,at in ((NEUTRAL,0),(NEUTRAL,.51),(RIGHT,.6),(LOWER,.7),(NEUTRAL,.8),(NEUTRAL,.96),(LOWER,1),(NEUTRAL,1.1)):
            self.assertFalse(gate.feed(value,at))
        self.assertFalse(gate.feed(NEUTRAL,1.59))
        self.assertTrue(gate.feed(NEUTRAL,1.61))
        self.assertEqual([v['stage'] for v in gate.transitions],list(range(5)))

    def test_stick_motion_resets_final_quiet(self):
        gate=Liveness();gate.stage=4
        gate.feed(NEUTRAL,0);gate.feed(b'other',.4);gate.feed(NEUTRAL,.5)
        self.assertFalse(gate.feed(NEUTRAL,.9));self.assertTrue(gate.feed(NEUTRAL,1.01))

    def test_clock_reversal_rejected(self):
        gate=Liveness();gate.feed(NEUTRAL,1)
        with self.assertRaises(ValueError):gate.feed(NEUTRAL,0)

if __name__=='__main__':unittest.main()
