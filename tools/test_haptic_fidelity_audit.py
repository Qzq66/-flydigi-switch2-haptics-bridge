"""Check numerical audit boundaries, not actuator performance."""
import unittest
from audit_haptic_fidelity import analyze

def event(word,at=0):return dict(at_us=at,motors=(word.to_bytes(4,'little')*2).hex(),flags=7)

class FidelityAudit(unittest.TestCase):
    def test_known_absolute_frequency_and_amplitude_bound(self):
        word=(1<<30)|(16<<23)|(64<<16)|(64<<2)
        sides=analyze([event(word)],0)
        for side in sides:
            self.assertEqual(side['active_frequency_histogram_hz'],[dict(hz=160.0,groups=1)])
            self.assertEqual(side['maximum_sum_of_band_amplitudes'],2**(-3.9375))
            self.assertEqual(side['legacy_gain5_groups_guaranteed_round_to_zero'],1)
            self.assertLess(side['legacy_gain5_peak_code_bound'],.5)

    def test_inactive_high_frequency_is_not_counted(self):
        word=(1<<30)|(64<<16)|(127<<2)
        for side in analyze([event(word)],0):
            self.assertEqual(side['active_parameter_groups'],0)
            self.assertEqual(side['active_band_groups_at_or_above_500_hz'],0)

    def test_active_high_frequency_is_flagged(self):
        word=(1<<30)|(64<<16)|(127<<9)|(127<<2)
        for side in analyze([event(word)],0):
            self.assertEqual(side['active_band_groups_at_or_above_500_hz'],1)
            self.assertGreater(side['active_frequency_histogram_hz'][0]['hz'],500)

    def test_prearm_disabled_and_no_new_word_do_not_create_activity(self):
        active=(1<<30)|(16<<23)|(64<<16)|(64<<2)
        rows=[event(active),event(0,10000),dict(event(active,20000),flags=3)]
        for side in analyze(rows,1):
            self.assertEqual(side['active_parameter_groups'],0)
            self.assertEqual(side['word_formats']['no_new_samples'],1)

if __name__=='__main__':unittest.main()
