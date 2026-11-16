"""Pure safety, frequency and ordered-dose checks for amplitude comparison."""
import copy,math,unittest
import test_fidelity_ab as base
from amplitude_ab_plan import build_plan,validate_plan,tone

class AmplitudeAB(base.AB):
    @classmethod
    def setUpClass(cls):cls.plan=build_plan()
    def test_plan_is_fixed_source_bounded_and_complete(self):
        p=self.plan;validate_plan(p)
        self.assertEqual([s['frequency_hz'] for s in p['segments']],[160,160])
        self.assertEqual([s['samples_per_side'] for s in p['segments']],[208,208])
        self.assertEqual([s['peak_code'] for s in p['segments']],[4,8])
        self.assertEqual([s['squared_code_sum'] for s in p['segments']],[[1632,1632],[6496,6496]])
        self.assertEqual(p['squared_code_sum_per_side'],[8128,8128]);self.assertEqual(p['total_samples_per_side'],416)
        for s in p['segments']:
            self.assertEqual(s['pcm'][0],s['pcm'][1]);self.assertEqual(s['pcm'][0][-8:],[128]*8)
        self.assertFalse(p['pico_access']);self.assertFalse(p['switch_access'])
    def test_tampered_pcm_or_limits_rejected(self):
        for field,value in [('inter_segment_silence_seconds',0),('maximum_offset',12),('preparation_seconds',0)]:
            p=copy.deepcopy(self.plan);p[field]=value
            with self.assertRaises(ValueError):validate_plan(p)
        p=copy.deepcopy(self.plan);p['segments'][0]['frequency_hz']=80
        with self.assertRaises(ValueError):validate_plan(p)
    def test_frequency_stays_fixed_at_both_amplitudes(self):
        for peak in (4,8):
            x=[v-128 for v in tone(peak)[:200]]
            powers={f:sum(v*math.cos(2*math.pi*f*n/1000) for n,v in enumerate(x))**2+sum(v*math.sin(2*math.pi*f*n/1000) for n,v in enumerate(x))**2 for f in range(5,500,5)}
            self.assertEqual(max(powers,key=powers.get),160)
            self.assertEqual(sum(x),0)
    def test_unreviewed_or_noninteger_amplitudes_rejected(self):
        for peak in (0,12,4.0,True,float('nan')):
            with self.assertRaises(ValueError):tone(peak)
if __name__=='__main__':unittest.main()
