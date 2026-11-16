"""Injected lifecycle, recorded source selection, and independent acceptance gates."""
import copy,unittest
from fidelity_network_session import ROOT,StreamSession,build_network_plan,validate_network_plan,validate_baseline_refresh,child_succeeded,program_succeeded
import json
from test_live_fidelity_candidate import frame,event,absolute,NEUTRAL
from live_fidelity_candidate import LiveFidelityRenderer,BridgeFault

class Clock:
    def __init__(self):self.now=0.
    def __call__(self):return self.now
    def pause(self,n):self.now+=n

class Network(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.plan=build_network_plan()

    def make(self,enable_error=False,write_error=False,stop_ack=True):
        clock=Clock();calls=[]
        def enable():
            calls.append(('enable',clock()))
            if enable_error:raise RuntimeError('enable failed')
        def send(l,r):
            calls.append(('send',clock()))
            if write_error:raise RuntimeError('write failed')
        def stop():calls.append(('stop',clock()));return dict(runtime_disable_ack=stop_ack)
        s=StreamSession(enable,send,stop,clock,clock.pause);s.feed(frame(0))
        return s,clock,calls

    def finish(self):
        s,clock,calls=self.make();s.arm()
        for seq,ms in enumerate(range(0,328,8)):
            clock.now=.064+ms/1000
            s.feed(frame(clock(),[event(seq,ms*1000,absolute() if ms<296 else NEUTRAL)]))
            if s.tick(clock()) is None:break
        return s,clock,calls

    def test_selected_source_starts_absolute_and_ends_neutral(self):
        p=self.plan;self.assertEqual(len(p['events']),21);self.assertEqual(p['events'][0]['at_us'],0)
        self.assertEqual(p['events'][-1]['at_us'],296016);self.assertFalse(p['flash_write']);validate_network_plan(p)

    def test_plan_tamper_rejected(self):
        for name,value in (('expected_flash_generation',19),('maximum_output_lateness_seconds',.02),('flash_write',True)):
            p=copy.deepcopy(self.plan);p[name]=value
            with self.assertRaises(ValueError):validate_network_plan(p)
        p=copy.deepcopy(self.plan);p['events'][0]['motors']='00'*8
        with self.assertRaises(ValueError):validate_network_plan(p)

    def test_explicit_journal_only_refresh_is_source_bound(self):
        name='docs/V043_READY_BASELINE_20261025-141518.json';p=build_network_plan(name);validate_network_plan(p)
        self.assertEqual(p['expected_flash_generation'],21);self.assertEqual(p['events'],self.plan['events'])
        p['baseline_refresh']['sha256']='changed'
        with self.assertRaises(ValueError):validate_network_plan(p)

    def test_refresh_refuses_program_change_missing_physical_proof_or_other_generation(self):
        good=json.loads((ROOT/'docs/V043_READY_BASELINE_20261025-141518.json').read_text())
        validate_baseline_refresh(good)
        for k,v in dict(previous_generation=19,baseline_generation=22,outside_journal_unchanged=False,
            physical_full_readback_verified=False,flash_write=True,firmware_sha256='changed',full_flash_sha256='changed').items():
            altered=dict(good);altered[k]=v
            with self.assertRaises(ValueError):validate_baseline_refresh(altered)

    def test_final_block_drains_and_stops_once(self):
        s,clock,calls=self.finish();self.assertIsNone(s.fault);self.assertTrue(s.summary()['output_stop_confirmed'])
        self.assertEqual(s.renderer.active_total,[296,296]);self.assertEqual(sum(k=='stop' for k,t in calls),1)
        sent=[t for k,t in calls if k=='send'];stopped=[t for k,t in calls if k=='stop']
        self.assertGreaterEqual(stopped[0]-sent[-1],.008-1e-9);s.stop();self.assertEqual(sum(k=='stop' for k,t in calls),1)

    def test_normal_stop_does_not_end_collection_and_terminal_preserves_completion(self):
        s,clock,calls=self.finish();count=len(s.events);s.feed(frame(clock()+.004,[event(count,328000,NEUTRAL)]))
        self.assertEqual(len(s.events),count+1);s.feed(frame(clock()+.008,flags=25))
        self.assertEqual(s.renderer.muted_reason,'single bilateral episode completed');self.assertIsNone(s.tick(clock()+.008))
        self.assertEqual(sum(k=='stop' for k,t in calls),1)

    def test_enable_failure_still_attempts_confirmed_stop(self):
        s,clock,calls=self.make(enable_error=True)
        with self.assertRaisesRegex(RuntimeError,'enable failed'):s.arm()
        self.assertEqual([k for k,t in calls],['enable','stop']);self.assertTrue(s.summary()['output_stop_confirmed'])

    def test_write_failure_aborts_without_more_frames(self):
        s,clock,calls=self.make(write_error=True);s.arm();clock.now=.064;s.feed(frame(clock()));self.assertIsNone(s.tick(clock()))
        self.assertIn('write failed',s.fault);s.tick(.072);self.assertEqual([k for k,t in calls],['enable','send','stop'])

    def test_failed_stop_remains_dirty_and_retry_cannot_erase_failure(self):
        s,clock,calls=self.make(stop_ack=False);s.arm()
        with self.assertRaisesRegex(BridgeFault,'unconfirmed'):s.stop()
        self.assertTrue(s.dirty);s.stop_output=lambda:dict(runtime_disable_ack=True);s.stop()
        self.assertFalse(s.dirty);self.assertIsNotNone(s.cleanup_error)

    def test_cancel_stops_and_fault_latches(self):
        s,clock,calls=self.make();s.arm();s.abort(RuntimeError('cancel'));s.feed(frame(.01));s.tick(.064)
        self.assertIn('cancel',s.fault);self.assertEqual(s.frames,0);self.assertEqual([k for k,t in calls],['enable','stop'])

    def test_archive_capacity_is_explicit_failure(self):
        s,clock,calls=self.make();s.arm()
        s.feed(frame(0,[event(i,0,NEUTRAL) for i in range(257)]))
        self.assertIn('capacity',s.fault);self.assertEqual(len(s.events),256);self.assertTrue(s.summary()['output_stop_confirmed'])

    def test_real_dispatch_clock_is_separate_from_pcm_grid(self):
        s,clock,calls=self.make();s.arm();clock.now=.066;s.feed(frame(.065));s.tick(.064)
        self.assertIsNone(s.fault);self.assertEqual(s.frames,1)
        s.renderer.feed(frame(.067))
        with self.assertRaisesRegex(BridgeFault,'heartbeat'):s.renderer.block(.072,observed_at=.148)

    def test_dispatch_time_cannot_reverse(self):
        r=LiveFidelityRenderer();r.feed(frame(0));r.arm(0)
        with self.assertRaisesRegex(BridgeFault,'dispatch'):r.block(.064,observed_at=.063)

    def test_complete_selected_words_through_separate_collector_and_output_clocks(self):
        s,clock,calls=self.make();s.arm();index=0;next_output=.064
        for ms in range(0,800,4):
            batch=[]
            while index<len(self.plan['events']) and 100000+self.plan['events'][index]['at_us']<=ms*1000:
                word=self.plan['events'][index];batch.append(event(index,100000+word['at_us'],bytes.fromhex(word['motors'])));index+=1
            clock.now=ms/1000+.001;s.feed(frame(ms/1000,batch))
            if clock()>=next_output and s.dirty:s.tick(next_output);next_output+=.008
            if s.stopped_at is not None:break
        self.assertIsNone(s.fault);self.assertEqual(index,21)
        self.assertTrue(all(296<=n<=297 for n in s.renderer.active_total));self.assertLessEqual(max(s.renderer.dose),8000)
        self.assertEqual(s.renderer.muted_reason,'single bilateral episode completed')
        self.assertEqual([e['motors'] for e in s.events],[e['motors'] for e in self.plan['events']])
        # Collector heartbeats continue after the 90ms simulated stop ACK.
        clock.pause(.09)
        for n in range(65):
            clock.pause(.004);s.feed(frame(clock()))
        s.feed(frame(clock(),flags=25));self.assertIsNone(s.fault)
        self.assertEqual(sum(k=='stop' for k,t in calls),1)

    def accepted(self):
        p=self.plan;fields=[e['motors'] for e in p['events']];prefix=[NEUTRAL.hex()]
        return dict(status='PASSED_RAM_WIFI_FIDELITY_REPLAY_CHILD',manual_armed=True,output_stop_confirmed=True,
            terminal_received=True,terminal_ack_replied=True,collector_ended=True,timer_released=True,pico_ram_reset_requested=True,
            snapshot_phase_confirmed=True,injector_done=True,injector_joined=True,injector_error=None,injector_cancelled=False,
            all_motor_fields_exact=True,sequence_contiguous=True,flash_write=False,actual_switch_game=False,persistent_flydigi_commands=0,
            initial_motor_fields=prefix,sent_motor_fields=fields,events=[dict(sequence=i,motors=m) for i,m in enumerate(prefix+fields)],
            muted_reason='single bilateral episode completed',active_ms=[296,296],squared_code_sum=[5615,5615],peak_code=9,output_frames=60,
            injection_lateness_seconds=[.001]*len(fields),output_lateness_seconds=[.001]*60,
            injection_write_seconds=[.001]*len(fields),output_write_seconds=[.001]*60,
            input_calls_after_output_stop=10,input_time_after_output_stop=.245,pico_input_updates_after_output_stop=10)

    def test_strict_child_gate_rejects_partial_or_unsafe_evidence(self):
        c=self.accepted();self.assertTrue(child_succeeded(c,self.plan))
        cases={'manual_armed':False,'terminal_ack_replied':False,'output_fault':'timeout','cleanup_error':'failed stop',
            'pico_ram_reset_requested':False,'timer_released':False,'input_calls_after_output_stop':4,'input_time_after_output_stop':.1,
            'pico_input_updates_after_output_stop':0,'active_ms':[321,296],'squared_code_sum':[8001,5615],'peak_code':13,
            'injection_lateness_seconds':[.005]*21,'output_lateness_seconds':[float('nan')]*60,
            'initial_motor_fields':[absolute().hex()],'sent_motor_fields':c['sent_motor_fields'][:-1],
            'flash_write':True,'error':'failure','events':[]}
        cases.update(snapshot_phase_confirmed=False,injector_done=False,injector_joined=False,injector_error='write failed',injector_cancelled=True,injection_write_seconds=[],output_write_seconds=[.081]*60)
        for k,v in cases.items():
            with self.subTest(k=k):
                altered=copy.deepcopy(c);altered[k]=v;self.assertFalse(child_succeeded(altered,self.plan))
        self.assertFalse(child_succeeded({},self.plan))

    def test_parent_requires_actual_before_after_flash_and_configuration_evidence(self):
        p=self.plan;r=dict(child_exit=0,guardian_killed_child=False,child=self.accepted(),runtime_disable_ack=True,
            configuration_unchanged=True,full_flash_after_matches=True,flash_before=dict(verified=True,baseline_generation=20,installed_snapshot_sha256=p['expected_full_flash_sha256']),
            flash_write=False,actual_switch_game=False,automatic_resume=False,persistent_flydigi_commands=0,ram_image_sha256=p['ram_uf2_sha256'])
        self.assertTrue(program_succeeded(r,p))
        for k,v in dict(child_exit=1,guardian_killed_child=True,full_flash_after_matches=False,configuration_unchanged=False,
            flash_before={},runtime_disable_ack=False,flash_cleanup_error='mismatch',ram_image_sha256='changed').items():
            altered=copy.deepcopy(r);altered[k]=v;self.assertFalse(program_succeeded(altered,p),k)

if __name__=='__main__':unittest.main()
