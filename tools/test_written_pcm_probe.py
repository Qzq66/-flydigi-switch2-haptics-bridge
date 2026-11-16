"""No hardware: bounded hashes, protocol parity, failures and stop propagation."""
import ast,copy,hashlib,json,pathlib,unittest
from written_pcm_probe import WrittenPCMProbe,encode_report,parse_report
from written_pcm_validation import assess_written,reference
from audit_game_parameter_mapping import emitted_timelines,core_reference
from fidelity_network_session import StreamSession
ROOT=pathlib.Path(__file__).resolve().parents[1]

class WrittenPCM(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree=ast.parse((ROOT/'handoff/2026-10-22/work/flydigi-safe-waveform.py').read_text(encoding='utf-8'))
        pure=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('packet','waveform')]
        if len(pure)!=2:raise ValueError('Expected two immutable pure packet helpers')
        namespace={};exec(compile(ast.Module(body=pure,type_ignores=[]),'accepted-pure-packet-helpers','exec'),namespace)
        cls.accepted_waveform=staticmethod(namespace['waveform'])
    def probe(self,limit=1900):
        sent=[]
        def write(report):sent.append(report)
        return WrittenPCMProbe(write,limit,clock=lambda:0.),sent
    def test_encoder_and_parser_match_accepted_packet_helpers(self):
        for left,right in [([128]*8,[128]*8),([128,129,127,132,124,140,116,128],[130,126,128,139,117,136,120,128])]:
            wire=self.accepted_waveform(left,right,maximum_offset=12)
            self.assertEqual(wire,encode_report(left,right));self.assertEqual(parse_report(wire),(bytes(left),bytes(right)))
    def test_hashes_order_and_statistics_after_success(self):
        p,sent=self.probe();l=[128,129,127,132,124,136,120,128];r=list(reversed(l))
        wire=encode_report(l,r);p.send(wire);p.send(wire);s=p.snapshot()
        self.assertTrue(s['complete']);self.assertEqual(len(sent),2)
        self.assertEqual(s['left_sha256'],hashlib.sha256(bytes(l+l)).hexdigest())
        self.assertEqual(s['right_sha256'],hashlib.sha256(bytes(r+r)).hexdigest())
        self.assertEqual(s['report_sha256'],hashlib.sha256(wire+wire).hexdigest())
        self.assertEqual(s['samples_per_side'],16);self.assertEqual(s['squared_code_sum'],[2*sum((v-128)**2 for v in l)]*2)
    def test_writer_exception_is_not_a_recorded_success_or_retried(self):
        calls=[]
        def write(data):calls.append(data);raise OSError('simulated partial write')
        p=WrittenPCMProbe(write,clock=lambda:0.);wire=encode_report([128]*8,[128]*8)
        with self.assertRaises(OSError):p.send(wire)
        with self.assertRaisesRegex(RuntimeError,'latched'):p.send(wire)
        s=p.snapshot();self.assertEqual(len(calls),1);self.assertEqual(s['recorded_frames'],0);self.assertTrue(s['possible_partial_or_unconfirmed_write']);self.assertFalse(s['complete'])
    def test_changed_writer_return_contract_is_uncertain(self):
        p=WrittenPCMProbe(lambda data:32,clock=lambda:0.)
        with self.assertRaises(RuntimeError):p.send(encode_report([128]*8,[128]*8))
        self.assertEqual(p.snapshot()['writer_successes'],0);self.assertFalse(p.snapshot()['complete'])
    def test_capacity_rejects_before_next_write(self):
        p,sent=self.probe(2);wire=encode_report([128]*8,[128]*8)
        p.send(wire);p.send(wire)
        with self.assertRaisesRegex(ValueError,'capacity'):p.send(wire)
        self.assertEqual(len(sent),2);self.assertEqual(p.snapshot()['recorded_frames'],2)
    def test_default_capacity_is_bounded_with_no_pcm_history(self):
        p,sent=self.probe();wire=encode_report([128]*8,[128]*8)
        for i in range(1900):p.send(wire)
        self.assertEqual(p.snapshot()['samples_per_side'],15200)
        with self.assertRaises(ValueError):p.send(wire)
        self.assertFalse(hasattr(p,'rows'));self.assertFalse(hasattr(p,'reports'))
    def test_dose_guard_precedes_write(self):
        p,sent=self.probe();wire=encode_report([140]*8,[116]*8)
        for i in range(6):p.send(wire)
        with self.assertRaisesRegex(ValueError,'energy'):p.send(wire)
        self.assertEqual(len(sent),6);self.assertEqual(p.snapshot()['squared_code_sum'],[6912,6912])
    def test_malformed_reports_never_reach_writer(self):
        valid=encode_report([128]*8,[128]*8)
        cases=[valid[:-1],bytearray(valid),bytes([1])+valid[1:]]
        for index,value in [(3,0x53),(5,0x80),(6,129),(7,141),(30,1)]:
            data=bytearray(valid);data[index]=value;data[32]=sum(data[3:32])&255;cases.append(bytes(data))
        data=bytearray(valid);data[32]^=1;cases.append(bytes(data))
        for wire in cases:
            p,sent=self.probe()
            with self.assertRaises(ValueError):p.send(wire)
            self.assertEqual(sent,[]);self.assertFalse(p.snapshot()['complete'])
    def test_invalid_capacity_is_rejected(self):
        for limit in [0,1901,True,1.5]:
            with self.assertRaises(ValueError):WrittenPCMProbe(lambda r:None,limit)
    def test_observer_cost_excludes_writer_time(self):
        ticks=iter([0.,.0001,.0021,.0023]);p=WrittenPCMProbe(lambda r:None,clock=lambda:next(ticks))
        p.send(encode_report([128]*8,[128]*8));s=p.snapshot()
        self.assertAlmostEqual(s['maximum_writer_call_seconds'],.002);self.assertAlmostEqual(s['maximum_observer_seconds'],.0003)
    def test_clock_reversal_before_write_is_rejected(self):
        ticks=iter([1.,.5]);calls=[];p=WrittenPCMProbe(lambda r:calls.append(r),clock=lambda:next(ticks))
        with self.assertRaisesRegex(ValueError,'clock'):p.send(encode_report([128]*8,[128]*8))
        self.assertEqual(calls,[])
    def failing_hash(self):
        class Hash:
            def copy(self):raise RuntimeError('simulated observer failure')
            def hexdigest(self):return hashlib.sha256().hexdigest()
        return Hash()
    def test_post_write_observer_failure_is_not_hidden(self):
        p,sent=self.probe();p._left=self.failing_hash()
        with self.assertRaisesRegex(RuntimeError,'observer failure'):p.send(encode_report([128]*8,[128]*8))
        s=p.snapshot();self.assertEqual(len(sent),1);self.assertEqual(s['writer_successes'],1);self.assertEqual(s['recorded_frames'],0);self.assertEqual(s['record_errors'],1);self.assertFalse(s['complete'])
    def test_post_write_failure_triggers_existing_session_stop(self):
        p,sent=self.probe();p._left=self.failing_hash();stops=[]
        class Renderer:
            armed=True
            def block(self,*args,**kwargs):return [[128]*8,[128]*8]
        s=StreamSession(lambda:None,lambda l,r:p.send(encode_report(l,r)),lambda:stops.append(1) or dict(runtime_disable_ack=True),clock=lambda:0.)
        s.renderer=Renderer();s.dirty=True;s.tick(0.)
        self.assertEqual(stops,[1]);self.assertEqual(s.frames,0);self.assertIsNotNone(s.fault);self.assertFalse(s.dirty)
    def test_two_real_source_fixtures_are_simulations_only(self):
        for tag in ('20261026-232226','20261027-212240'):
            child=copy.deepcopy(json.loads((ROOT/'docs'/('FIDELITY_GAME_RUN_'+tag+'.json')).read_text())['child'])
            timelines,start,end=emitted_timelines(child);pcm=core_reference(timelines,start,child['output_frames'])
            p,sent=self.probe()
            for i in range(0,len(pcm[0]),8):p.send(self.accepted_waveform(pcm[0][i:i+8],pcm[1][i:i+8],maximum_offset=12))
            child['written_pcm']=p.snapshot();self.assertTrue(assess_written(child)['passed']);self.assertEqual(len(sent),child['output_frames'])
    def test_hashes_detect_reordering_that_preserves_old_aggregate_metrics(self):
        child=copy.deepcopy(json.loads((ROOT/'docs/FIDELITY_GAME_RUN_20261027-212240.json').read_text())['child'])
        timelines,start,end=emitted_timelines(child);pcm=core_reference(timelines,start,child['output_frames'])
        index=next(i for i in range(len(pcm[0])-1) if i%8!=7 and pcm[0][i]!=pcm[0][i+1])
        pcm[0][index],pcm[0][index+1]=pcm[0][index+1],pcm[0][index]
        p,sent=self.probe()
        for i in range(0,len(pcm[0]),8):p.send(encode_report(pcm[0][i:i+8],pcm[1][i:i+8]))
        child['written_pcm']=p.snapshot();r=assess_written(child)
        self.assertFalse(r['passed']);self.assertTrue(r['checks']['squared_code_sum']);self.assertTrue(r['checks']['peak_per_side']);self.assertTrue(r['checks']['nonneutral_samples']);self.assertFalse(r['checks']['left_sha256']);self.assertFalse(r['checks']['report_sha256'])
    def test_missing_summary_cannot_pass(self):
        self.assertFalse(assess_written({})['passed'])

if __name__=='__main__':unittest.main()
