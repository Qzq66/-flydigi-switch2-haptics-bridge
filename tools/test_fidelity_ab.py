"""Reviewable A/B bounds and injected failures, with no hardware or sleeps."""
import copy,unittest
from fidelity_ab_plan import build_plan,validate_plan,play_segment,ab_child_succeeded

class Clock:
    def __init__(self,extra=0):self.now=0;self.extra=extra
    def __call__(self):return self.now
    def pause(self,seconds):self.now+=seconds+self.extra

class AB(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.plan=build_plan()

    def test_plan_is_fixed_source_bounded_and_complete(self):
        plan=self.plan;self.assertEqual(plan['source_journal_generation'],18)
        self.assertEqual([s['samples_per_side'] for s in plan['segments']],[120,312])
        self.assertEqual([s['peak_code'] for s in plan['segments']],[12,9])
        self.assertLessEqual(plan['total_samples_per_side'],440)
        self.assertTrue(all(d<=20000 for d in plan['squared_code_sum_per_side']))
        self.assertEqual(plan['b_source_activity_ms'],[296,296])
        validate_plan(plan)

    def test_tampered_pcm_or_limits_rejected(self):
        for field,value in (('inter_segment_silence_seconds',0),('maximum_offset',13),('gain_b',120)):
            p=copy.deepcopy(self.plan);p[field]=value
            with self.assertRaises(ValueError):validate_plan(p)
        p=copy.deepcopy(self.plan);p['segments'][1]['pcm'][0][10]+=1
        with self.assertRaises(ValueError):validate_plan(p)

    def run_segment(self,segment=None,extra=0,fail_send=False,fail_enable=False,fail_stop=False):
        clock=Clock(extra);trace=[]
        def enable():
            trace.append(('enable',clock()))
            if fail_enable:raise RuntimeError('enable failed')
        def send(left,right):
            trace.append(('send',clock()))
            if fail_send:raise RuntimeError('write failed')
        def stop():
            trace.append(('stop',clock()))
            if fail_stop:raise RuntimeError('stop failed')
        return clock,trace,lambda:play_segment(segment or self.plan['segments'][0],enable,send,stop,clock,clock.pause)

    def test_all_frames_end_with_eight_ms_drain_then_single_stop(self):
        for segment in self.plan['segments']:
            clock,trace,run=self.run_segment(segment);r=run()
            self.assertEqual(r['frames'],segment['samples_per_side']//8)
            self.assertEqual(sum(label=='stop' for label,t in trace),1)
            self.assertGreaterEqual(trace[-1][1]-trace[-2][1],.008-1e-9)
            self.assertGreaterEqual(clock(),segment['samples_per_side']/1000-1e-9)

    def test_late_scheduler_stops_without_burst_catchup(self):
        clock,trace,run=self.run_segment(extra=.020)
        with self.assertRaisesRegex(RuntimeError,'late'):run()
        self.assertEqual([name for name,t in trace],['enable','send','stop'])

    def test_enable_or_write_failure_still_stops_once(self):
        for kwargs in (dict(fail_enable=True),dict(fail_send=True)):
            clock,trace,run=self.run_segment(**kwargs)
            with self.assertRaises(RuntimeError):run()
            self.assertEqual(sum(name=='stop' for name,t in trace),1)
            self.assertEqual(trace[-1][0],'stop')

    def test_stop_failure_propagates(self):
        clock,trace,run=self.run_segment(fail_stop=True)
        with self.assertRaisesRegex(RuntimeError,'stop failed'):run()

    def test_invalid_pcm_refused_before_enabling(self):
        segment=copy.deepcopy(self.plan['segments'][0]);segment['pcm'][0][0]=141
        clock,trace,run=self.run_segment(segment)
        with self.assertRaises(ValueError):run()
        self.assertEqual(trace,[])

    def test_manual_cancel_prevents_more_blocks_and_stops(self):
        clock=Clock();trace=[];cancel=[False]
        def send(left,right):trace.append('send');cancel[0]=True
        with self.assertRaisesRegex(RuntimeError,'cancelled'):
            play_segment(self.plan['segments'][0],lambda:trace.append('enable'),send,lambda:trace.append('stop'),clock,clock.pause,cancelled=lambda:cancel[0])
        self.assertEqual(trace,['enable','send','stop'])
        trace.clear()
        with self.assertRaisesRegex(RuntimeError,'cancelled'):
            play_segment(self.plan['segments'][0],lambda:trace.append('enable'),send,lambda:trace.append('stop'),clock,clock.pause,cancelled=lambda:True)
        self.assertEqual(trace,[])

    def good(self):
        return dict(status='PASSED_FIDELITY_AB_CLIP_PROGRAM',manual_armed=True,timer_released=True,manual_accepted_at_monotonic=0,
            segments=[dict(label=s['label'],started_at_monotonic=start,stop=dict(runtime_disable_ack=True,confirmed_at_monotonic=start+1),playback=dict(frames=s['samples_per_side']//8,samples_per_side=s['samples_per_side'])) for s,start in zip(self.plan['segments'],(6,12))])

    def test_acceptance_requires_both_stops_complete_frames_gap_and_manual_arm(self):
        self.assertTrue(ab_child_succeeded(self.good(),0,self.plan))
        for name,value in (('manual_armed',False),('timer_released',False),('error','fault')):
            c=self.good();c[name]=value;self.assertFalse(ab_child_succeeded(c,0,self.plan))
        for mutate in (lambda c:c['segments'][0]['stop'].update(runtime_disable_ack=False),lambda c:c['segments'][1]['playback'].update(frames=1),lambda c:c['segments'][1].update(started_at_monotonic=11.999),lambda c:c['segments'][0].update(started_at_monotonic=5.999),lambda c:c['segments'][1].update(label='A')):
            c=self.good();mutate(c);self.assertFalse(ab_child_succeeded(c,0,self.plan))
        self.assertFalse(ab_child_succeeded(self.good(),1,self.plan));self.assertFalse(ab_child_succeeded(self.good(),0,self.plan,killed=True))

if __name__=='__main__':unittest.main()
