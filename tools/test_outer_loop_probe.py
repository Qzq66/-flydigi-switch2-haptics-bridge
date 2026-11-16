import types,unittest
from outer_loop_probe import OuterLoopProbe,TimeProxy,MarkerPath,PhasePath,GameProxy
class Tests(unittest.TestCase):
    def setUp(self):self.now=0.;self.p=OuterLoopProbe(lambda:self.now)
    def advance(self,n):self.now+=n;return 'value'
    def test_sleep_stall_identified(self):
        self.p.after_tick();t=TimeProxy(types.SimpleNamespace(sleep=lambda n:self.advance(n+.007)),self.p);t.sleep(.001);g=self.p.before_tick();self.assertAlmostEqual(g['seconds'],.008);self.assertAlmostEqual(g['phase_seconds']['sleep_or_wakeup'],.008);self.assertEqual(g['unattributed_seconds'],0)
    def test_cancel_query_stall_identified(self):
        fake=types.SimpleNamespace(exists=lambda:self.advance(.008),with_suffix=lambda s:fake);self.p.after_tick();MarkerPath(fake,self.p).with_suffix('.cancel').exists();g=self.p.before_tick();self.assertAlmostEqual(g['phase_seconds']['cancel_stat'],.008)
    def test_input_and_enqueue_separately_identified(self):
        self.p.after_tick();game=GameProxy(types.SimpleNamespace(feed=lambda f:self.advance(.003)),self.p);game.feed({});PhasePath(types.SimpleNamespace(write_text=lambda s:self.advance(.005)),self.p).write_text('{}');g=self.p.before_tick();self.assertAlmostEqual(g['phase_seconds']['input_processing'],.003);self.assertAlmostEqual(g['phase_seconds']['phase_enqueue'],.005)
    def test_uninstrumented_gap_stays_unknown(self):
        self.p.after_tick();self.advance(.0087);g=self.p.before_tick();self.assertAlmostEqual(g['unattributed_seconds'],.0087);self.assertEqual(g['covered_union_seconds'],0)
    def test_nested_spans_do_not_double_count_coverage(self):
        self.p.after_tick()
        def outer():self.advance(.001);self.p.call('phase_enqueue',self.advance,.002)
        self.p.call('input_processing',outer);g=self.p.before_tick();self.assertAlmostEqual(g['covered_union_seconds'],.003);self.assertEqual(g['unattributed_seconds'],0)
    def test_capacity_marks_missing_context(self):
        p=OuterLoopProbe(lambda:self.now,capacity=8);p.after_tick()
        for _ in range(20):p.call('input_processing',self.advance,.001)
        g=p.before_tick();self.assertFalse(g['context_complete']);self.assertEqual(p.summary()['retained'],8)
    def test_first_stall_evidence_preserved(self):
        self.p.after_tick();self.p.call('cancel_stat',self.advance,.005);self.p.before_tick();first=self.p.first_slow_gap;self.p.after_tick();self.p.call('sleep_or_wakeup',self.advance,.009);self.p.before_tick();self.assertIs(self.p.first_slow_gap,first);self.assertAlmostEqual(self.p.maximum_gap['seconds'],.009)
    def test_exception_preserved_and_recorded(self):
        def fail():raise OSError('injected')
        with self.assertRaises(OSError):self.p.call('cancel_stat',fail)
        self.assertEqual(self.p.rows[-1]['error'],'OSError')
    def test_wrappers_preserve_call_order_and_returns(self):
        calls=[];g=GameProxy(types.SimpleNamespace(feed=lambda f:calls.append('feed'),tick=lambda:calls.append('tick')),self.p);g.feed({});g.tick();self.assertEqual(calls,['feed','tick'])
    def test_no_raw_path_or_payload_recorded(self):
        self.p.call('phase_enqueue',lambda secret:'ok','do-not-record');self.assertNotIn('do-not-record',str(self.p.summary()));self.assertNotIn('do-not-record',str(list(self.p.rows)))
    def test_long_run_memory_and_report_size_bounded(self):
        import json
        self.p.after_tick();self.p.call('cancel_stat',self.advance,.005);self.p.before_tick()
        for i in range(10000):
            self.p.after_tick();self.p.call('input_processing',self.advance,.001);self.p.before_tick()
        self.assertEqual(self.p.summary()['retained'],256);self.assertLess(len(json.dumps(self.p.summary()).encode()),262144);self.assertAlmostEqual(self.p.first_slow_gap['seconds'],.005)
if __name__=='__main__':unittest.main()
