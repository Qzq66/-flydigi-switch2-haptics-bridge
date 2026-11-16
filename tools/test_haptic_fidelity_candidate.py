"""Independent spectral, envelope, timing and rejection checks; no hardware."""
import math,unittest
from haptic_fidelity_candidate import ZERO,reconstruct,decode_timeline

def point(at,amp=.04,hz=100,high_amp=0,high_hz=200):
    return dict(at_us=at,low_amplitude=amp,low_hz=hz,high_amplitude=high_amp,high_hz=high_hz)

def magnitude(values,hz):
    return abs(sum(v*complex(math.cos(-2*math.pi*hz*n/1000),math.sin(-2*math.pi*hz*n/1000)) for n,v in enumerate(values)))

class Candidate(unittest.TestCase):
    def test_two_frequencies_survive_quantization_with_independent_sides(self):
        left=[point(0,.04,100,.02,200),dict(at_us=1000000,**ZERO)]
        right=[point(0,.03,150),dict(at_us=1000000,**ZERO)]
        r=reconstruct([left,right],0,1001000)
        l=[v-128 for v in r['pcm'][0][:1000]];rr=[v-128 for v in r['pcm'][1][:1000]]
        self.assertGreater(magnitude(l,100),10*magnitude(l,150))
        self.assertGreater(magnitude(l,200),10*magnitude(l,150))
        self.assertGreater(magnitude(rr,150),10*magnitude(rr,100))
        self.assertAlmostEqual(magnitude(l,100)/magnitude(l,200),2,delta=.3)
        self.assertLessEqual(max(abs(v) for v in l+rr),12)

    def test_fixed_gain_preserves_envelope_ratio(self):
        t=[point(0,.04),point(100000,.02),dict(at_us=200000,**ZERO)]
        r=reconstruct([t,t],0,201000)
        x=r['reference'][0];rms=lambda a:math.sqrt(sum(v*v for v in a)/len(a))
        self.assertAlmostEqual(rms(x[:100])/rms(x[100:200]),2,places=10)
        self.assertEqual(r['pcm'][0][-1],128)
        self.assertLessEqual(r['sides'][0]['quantization_error_max'],.5)

    def test_frequency_update_keeps_phase(self):
        t=[point(0,.04,100),point(1000,.04,150),dict(at_us=3000,**ZERO)]
        r=reconstruct([t,t],0,4000)
        self.assertAlmostEqual(r['reference'][0][1],96*.04*math.sin(.2*math.pi))
        self.assertAlmostEqual(r['reference'][0][2],96*.04*math.sin(.5*math.pi))

    def test_no_new_word_holds_state_and_final_neutral_ends_it(self):
        word=(1<<30)|(16<<23)|(64<<16)|(64<<2)
        raw=lambda w:(w.to_bytes(4,'little')*2).hex()
        events=[dict(sequence=i,at_us=at,motors=raw(w),flags=7) for i,(at,w) in enumerate(((0,word),(10000,0),(20000,int.from_bytes(bytes.fromhex('00014040'),'little'))))]
        timelines,conflicts=decode_timeline(events,0);r=reconstruct(timelines,0,21000)
        self.assertEqual(r['sides'][0]['active_ms'],20)
        self.assertEqual(r['pcm'][0][20],128)

    def test_disable_with_no_groups_cancels_held_activity(self):
        word=(1<<30)|(16<<23)|(64<<16)|(64<<2)
        events=[dict(sequence=0,at_us=0,motors=(word.to_bytes(4,'little')*2).hex(),flags=7),dict(sequence=1,at_us=10000,motors='00'*8,flags=3)]
        timelines,_=decode_timeline(events,0);r=reconstruct(timelines,0,12000)
        self.assertEqual(r['sides'][0]['active_ms'],10)
        self.assertEqual(r['pcm'][0][-2:],[128,128])

    def test_high_frequency_peak_overflow_and_nonfinite_parameters_rejected(self):
        for p in (point(0,.04,500),point(0,.04,700),point(0,.2),point(0,float('nan')),point(float('nan'))):
            with self.subTest(point=p),self.assertRaises(ValueError):reconstruct([[p],[p]],0,1000)
        with self.assertRaises(ValueError):reconstruct([[point(0)],[point(0)]],0,1000,gain=float('inf'))

    def test_postarm_overlap_missing_sequence_and_truncated_tail_rejected(self):
        # three_7bit pulse expands to groups at 0/5/10ms, then next record at 1ms.
        events=[dict(sequence=0,at_us=0,motors='801860b2801860b2',flags=7),dict(sequence=1,at_us=1000,motors='0001404000014040',flags=7)]
        with self.assertRaisesRegex(ValueError,'timing'):decode_timeline(events,0)
        events[1]['sequence']=2
        with self.assertRaisesRegex(ValueError,'sequence'):decode_timeline(events,0)
        word=(1<<30)|(16<<23)|(64<<16)|(64<<2)
        with self.assertRaisesRegex(ValueError,'neutral'):decode_timeline([dict(sequence=0,at_us=0,motors=(word.to_bytes(4,'little')*2).hex(),flags=7)],0)

if __name__=='__main__':unittest.main()
