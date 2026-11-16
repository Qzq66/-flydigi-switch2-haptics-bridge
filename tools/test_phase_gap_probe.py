"""Injected phase timing, maximum retention and bounded snapshots; no I/O."""
import json,threading,unittest
from phase_gap_probe import PhaseGapProbe,GapObservedClient

class Clock:
    def __init__(self):self.now=0.
    def __call__(self):return self.now

class Client:
    def __init__(self,clock,results=None):self.clock=clock;self.results=list(results or []);self.calls=[];self.last=None;self.terminal_ack_replied=True
    def poll(self,*args,**kwargs):
        self.calls.append((args,kwargs));outcome,duration=self.results.pop(0);self.clock.now+=duration
        if isinstance(outcome,BaseException):raise outcome
        if outcome is None:return None
        self.last=dict(received_at=self.clock(),source_us=round(self.clock()*1e6)&0xffffffff,flags=7,events=[],boot=0,rtt_ms=duration*1000,private_payload='must-not-be-copied')
        return self.last

class PhaseTests(unittest.TestCase):
    def make(self,results):
        c=Clock();base=Client(c,results);sleeps=[]
        def sleep(seconds):sleeps.append(seconds);c.now+=.016
        return GapObservedClient(base,c,sleep),base,c,sleeps
    def test_returns_same_frame_and_delegates_arguments_without_retries(self):
        p,base,c,s=self.make([('frame',.002)])
        frame=p.poll(final_ack=True);self.assertIs(frame,base.last);self.assertEqual(base.calls,[((),{'final_ack':True})])
        d=p.snapshot()['phase_gap'];self.assertEqual(d['poll_calls'],1);self.assertEqual(d['frames'],1);self.assertNotIn('must-not-be-copied',json.dumps(d))
    def test_requested_and_observed_pause_are_distinct(self):
        p,b,c,s=self.make([('frame',.002)]);p.poll();p.pause(.004);d=p.snapshot()['phase_gap']
        self.assertEqual(s,[.004]);r=d['maximum_actual_pause'];self.assertAlmostEqual(r['duration_seconds'],.016);self.assertEqual(r['requested_seconds'],.004)
    def test_end_timestamp_precedes_observer_bookkeeping(self):
        c=Clock();p=PhaseGapProbe(c);p.begin('pause',.004);c.now=.004;ended=c();c.now=.020;p.finish(ended_at=ended)
        self.assertAlmostEqual(p.snapshot()['recent_events'][-1]['duration_seconds'],.004)
    def test_original_timeout_is_not_retried(self):
        p,b,c,s=self.make([(None,.062),('frame',.002)])
        self.assertIsNone(p.poll());self.assertEqual(len(b.calls),1);p.pause(.004);p.poll()
        d=p.snapshot();self.assertEqual(d['timeouts'],1);self.assertEqual(d['phase_gap']['timeouts'],1)
    def test_underlying_error_is_recorded_by_type_and_propagated(self):
        error=OSError('private-address-not-for-new-snapshot');p,b,c,s=self.make([(error,.01)])
        with self.assertRaises(OSError) as caught:p.poll()
        self.assertIs(caught.exception,error);d=p.snapshot()['phase_gap'];self.assertEqual(d['poll_errors'],1);self.assertNotIn('private-address',json.dumps(d));self.assertEqual(len(b.calls),1)
    def test_pause_error_is_not_swallowed(self):
        p,b,c,s=self.make([])
        def sleep(n):raise RuntimeError('sleep failed')
        p.sleep=sleep
        with self.assertRaises(RuntimeError):p.pause(.004)
        self.assertEqual(p.snapshot()['phase_gap']['pause_errors'],1)
    def record(self,p,c,kind='poll',duration=.001,frame=True):
        p.begin(kind,.004 if kind=='pause' else None);c.now+=duration
        f=dict(received_at=c(),source_us=round(c()*1e6)&0xffffffff,flags=7,events=[]) if frame and kind=='poll' else None
        p.finish(frame=f,ended_at=c())
    def test_global_max_context_survives_ring_overwrite_and_large_timeouts(self):
        c=Clock();p=PhaseGapProbe(c);self.record(p,c);self.record(p,c,duration=.15)
        anchor=p.snapshot()['protected_gap_event_index']
        for i in range(160):self.record(p,c,duration=.20,frame=False)
        d=p.snapshot();self.assertNotIn(anchor,[r['event_index'] for r in d['recent_events']]);self.assertIn(anchor,[x['anchor']['event_index'] for x in d['contexts']]);self.assertEqual(len(d['contexts']),8)
        self.record(p,c);d=p.snapshot();self.assertGreater(d['maximum_receive_gap']['row']['receive_gap_seconds'],30);self.assertIn(d['protected_gap_event_index'],[x['anchor']['event_index'] for x in d['contexts']])
    def test_partial_post_window_is_explicit_and_not_invented(self):
        c=Clock();p=PhaseGapProbe(c);self.record(p,c);self.record(p,c,duration=.1);d=p.snapshot();x=next(x for x in d['contexts'] if x['anchor']['event_index']==d['protected_gap_event_index'])
        self.assertFalse(x['post_complete']);self.assertEqual(x['post'],[])
        for i in range(8):self.record(p,c,kind='pause')
        d=p.snapshot();x=next(x for x in d['contexts'] if x['anchor']['event_index']==d['protected_gap_event_index']);self.assertTrue(x['post_complete']);self.assertTrue(all(r['event_index']>x['anchor']['event_index'] for r in x['post']))
    def test_budget_stops_before_another_underlying_poll(self):
        p,b,c,s=self.make([('frame',.001),('frame',.001)]);p.phase_gap=PhaseGapProbe(c,max_events=2);p.poll();p.pause(.004)
        with self.assertRaisesRegex(ValueError,'budget'):p.poll()
        self.assertEqual(len(b.calls),1);self.assertFalse(p.snapshot()['phase_gap']['healthy'])
    def test_snapshot_isolated_from_consumer_mutation(self):
        c=Clock();p=PhaseGapProbe(c);self.record(p,c);d=p.snapshot();d['recent_events'][0]['start']=-10
        self.assertEqual(p.snapshot()['recent_events'][0]['start'],0.)
    def test_inflight_phase_is_visible_separately_from_completed_counts(self):
        c=Clock();p=PhaseGapProbe(c);p.begin('poll');d=p.snapshot();self.assertEqual(d['poll_calls'],0);self.assertEqual(d['in_flight']['kind'],'poll');self.assertFalse(d['base_and_detail_same_instant'])
    def test_terminal_attempts_use_the_same_observed_poll(self):
        p,b,c,s=self.make([(None,.060),('frame',.001)]);self.assertIsNotNone(p.confirm_end());d=p.snapshot()['phase_gap'];self.assertEqual(d['poll_calls'],2);self.assertTrue(all(k=={'final_ack':True} for a,k in b.calls));self.assertEqual(d['pause_calls'],0)
    def test_clock_reversal_rejected_before_next_poll(self):
        p,b,c,s=self.make([('frame',.001),('frame',.001)]);p.poll();c.now=-1
        with self.assertRaisesRegex(ValueError,'clock'):p.poll()
        self.assertEqual(len(b.calls),1)
    def test_atomic_snapshot_counts_and_size_during_production(self):
        c=Clock();p=PhaseGapProbe(c);errors=[]
        def producer():
            try:
                for i in range(1000):self.record(p,c,duration=.06 if i%11==0 else .001);self.record(p,c,kind='pause',duration=.016)
            except BaseException as e:errors.append(e)
        thread=threading.Thread(target=producer);thread.start()
        while thread.is_alive():
            d=p.snapshot();self.assertTrue(d['snapshot_atomic']);self.assertEqual(d['recorded_events'],d['poll_calls']+d['pause_calls'])
        thread.join();self.assertEqual(errors,[]);d=p.snapshot();self.assertEqual(d['recorded_events'],2000);self.assertLessEqual(len(d['recent_events']),128);self.assertLessEqual(len(d['contexts']),8);self.assertLess(len(json.dumps(d,separators=(',',':')).encode()),262144)
    def test_invalid_capacities_do_not_allocate_unbounded_history(self):
        for cap in (0,65537,True,1.5):
            with self.assertRaises(ValueError):PhaseGapProbe(max_events=cap)

if __name__=='__main__':unittest.main()
