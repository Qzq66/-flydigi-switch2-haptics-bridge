"""Pure waveform, dose, stop and scheduler checks for frequency comparison."""
import copy,math,unittest
import test_fidelity_ab as base
from frequency_ab_plan import build_plan,validate_plan,tone

class FrequencyAB(base.AB):
    @classmethod
    def setUpClass(cls):cls.plan=build_plan()

    def test_plan_is_fixed_source_bounded_and_complete(self):
        p=self.plan;validate_plan(p)
        self.assertEqual([s['frequency_hz'] for s in p['segments']],[80,240])
        self.assertEqual([s['samples_per_side'] for s in p['segments']],[208,208])
        self.assertEqual([s['peak_code'] for s in p['segments']],[8,8])
        self.assertEqual(p['total_samples_per_side'],416)
        self.assertEqual(p['segments'][0]['squared_code_sum'],p['segments'][1]['squared_code_sum'])
        self.assertEqual(p['squared_code_sum_per_side'],[12992,12992])
        for s in p['segments']:
            self.assertEqual(s['pcm'][0],s['pcm'][1]);self.assertEqual(s['pcm'][0][-8:],[128]*8)
        self.assertFalse(p['pico_access']);self.assertFalse(p['switch_access'])

    def test_tampered_pcm_or_limits_rejected(self):
        for field,value in [('inter_segment_silence_seconds',0),('maximum_offset',12),('preparation_seconds',0)]:
            p=copy.deepcopy(self.plan);p[field]=value
            with self.assertRaises(ValueError):validate_plan(p)
        p=copy.deepcopy(self.plan);p['segments'][0]['pcm'][0][3]+=1
        with self.assertRaises(ValueError):validate_plan(p)

    def test_dominant_digital_frequency(self):
        for hz in (80,240):
            x=[v-128 for v in tone(hz)[:200]]
            powers={f:sum(v*math.cos(2*math.pi*f*n/1000) for n,v in enumerate(x))**2+sum(v*math.sin(2*math.pi*f*n/1000) for n,v in enumerate(x))**2 for f in range(5,500,5)}
            self.assertEqual(max(powers,key=powers.get),hz)
            self.assertGreater(powers[hz],100*max(v for f,v in powers.items() if f!=hz))

    def test_frequencies_outside_reviewed_pair_rejected(self):
        for hz in (0,160,500,float('nan')):
            with self.assertRaises(ValueError):tone(hz)

if __name__=='__main__':unittest.main()
