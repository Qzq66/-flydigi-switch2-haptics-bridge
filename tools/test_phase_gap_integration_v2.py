"""Accepted collector plus injected phase observer; no device or socket."""
import copy,pathlib,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'handoff/2026-10-22/work'))
from bridge_render import collect_frames
from phase_gap_probe_v2 import GapObservedClient
from phase_gap_validation_v2 import assess_phase_gap
from test_phase_gap_probe import Client,Clock

class Integration(unittest.TestCase):
    def test_missing_or_corrupt_rtt_rejected(self):
        for field in ('transport_receive_decode_seconds','poll_start_to_transport_timer_seconds','received_to_poll_end_seconds'):
            for value in (None,-1,float('nan'),.999):
                p,b,f=self.complete();d=p.snapshot();d['phase_gap']['maximum_receive_gap']['row'][field]=value
                self.assertFalse(assess_phase_gap({'transport_diagnostics':d})['passed'])
    def test_old_schema_rejected(self):
        p,b,f=self.complete();d=p.snapshot();d['phase_gap']['version']=1
        self.assertFalse(assess_phase_gap({'transport_diagnostics':d})['passed'])
    def complete(self):
        clock=Clock()
        class Terminal(Client):
            def poll(self,*args,**kwargs):
                frame=super().poll(*args,**kwargs)
                if len(self.calls)>=3:frame['flags']=25
                return frame
        base=Terminal(clock,[('frame',.001)]*4)
        p=GapObservedClient(base,clock,sleep=lambda n:setattr(clock,'now',clock.now+n));published=[]
        collect_frames(p,published.append,lambda:False,pause=p.pause)
        return p,base,published
    def test_collector_keeps_terminal_handshake_and_four_ms_request(self):
        p,base,published=self.complete();d=p.snapshot();phase=d['phase_gap']
        self.assertEqual(len(base.calls),4);self.assertEqual(phase['pause_calls'],2);self.assertEqual(phase['recorded_events'],6)
        self.assertEqual([r['requested_seconds'] for r in phase['recent_events'] if r['phase']=='pause'],[.004,.004])
        self.assertEqual(base.calls[-1],((),{'final_ack':True}));self.assertEqual(published[-2]['flags'],9);self.assertEqual(published[-1]['flags'],25)
        self.assertTrue(assess_phase_gap({'transport_diagnostics':d})['passed'])
    def test_missing_detail_cannot_pass(self):self.assertFalse(assess_phase_gap({})['passed'])
    def test_missing_maximum_context_cannot_pass(self):
        p,b,f=self.complete();d=p.snapshot();d['phase_gap']['contexts']=[]
        self.assertFalse(assess_phase_gap({'transport_diagnostics':d})['passed'])
    def test_mismatched_counter_cannot_pass(self):
        p,b,f=self.complete();d=p.snapshot();d['poll_calls']+=1
        self.assertFalse(assess_phase_gap({'transport_diagnostics':d})['passed'])
    def test_inflight_snapshot_is_not_final_acceptance(self):
        p,b,f=self.complete();p.phase_gap.begin('poll');d=p.snapshot()
        self.assertFalse(assess_phase_gap({'transport_diagnostics':d})['passed'])
    def test_corrupt_post_context_cannot_pass(self):
        p,b,f=self.complete();d=p.snapshot();c=d['phase_gap']['contexts'][0]
        c['post'].append(copy.deepcopy(c['anchor']))
        self.assertFalse(assess_phase_gap({'transport_diagnostics':d})['passed'])
    def test_budget_fault_propagates_out_of_accepted_collector(self):
        clock=Clock();base=Client(clock,[('frame',.001)]*2);p=GapObservedClient(base,clock,sleep=lambda n:setattr(clock,'now',clock.now+n),max_events=2)
        with self.assertRaisesRegex(ValueError,'budget'):collect_frames(p,lambda f:None,lambda:False,pause=p.pause)
        self.assertEqual(len(base.calls),1);self.assertFalse(p.snapshot()['phase_gap']['healthy'])

if __name__=='__main__':unittest.main()
