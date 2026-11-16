"""Game registration/arming/mute/transport and same-trial acceptance without I/O."""
import copy,unittest
from fidelity_game_policy import GameSession,build_game_plan,validate_game_plan,game_child_passed,game_parent_passed,can_click
from assess_fidelity_game import assess,source_reference
from test_fidelity_network import Clock
from test_live_fidelity_candidate import frame,event,absolute,NEUTRAL,BridgeFault

class Game(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.plan=build_game_plan()

    def make(self):
        clock=Clock();calls=[]
        def stop():calls.append(('stop',clock()));return dict(runtime_disable_ack=True)
        game=GameSession(lambda:calls.append(('enable',clock())),lambda l,r:calls.append(('send',clock())),stop,clock,clock.pause)
        game.feed(frame(0,[event(0,0,NEUTRAL)]));clock.now=.6;game.feed(frame(clock()))
        return game,clock,calls

    def complete(self):
        g,clock,calls=self.make();g.arm(True,.6)
        for seq,source in enumerate(range(600,1032,8),start=1):
            clock.now=g.target;raw=absolute() if 704<=source<1000 else NEUTRAL
            g.feed(frame(clock(),[event(seq,source*1000,raw)]));g.tick()
            if g.output.stopped_at is not None:break
        self.assertIsNone(g.output.fault);return g,clock,calls

    def test_plan_binds_full_replay_and_input_acceptance_without_modifying_old_entries(self):
        p=self.plan;validate_game_plan(p);self.assertEqual(p['expected_flash_generation'],22)
        self.assertTrue(p['manual_click_required']);self.assertFalse(p['host_flash_write']);self.assertTrue(p['firmware_log_write_expected'])
        self.assertEqual(p['limits']['maximum_events'],2725);self.assertEqual(p['arm_latest_seconds'],100)
        q=copy.deepcopy(p);q['limits']['maximum_offset']=13
        with self.assertRaises(ValueError):validate_game_plan(q)

    def test_registration_navigation_and_prearm_activity_never_send_a_waveform(self):
        g,clock,calls=self.make();clock.now=.61;g.feed(frame(clock(),[event(1,610000,absolute())]));g.tick()
        self.assertEqual(calls,[]);self.assertEqual(g.output.frames,0);self.assertFalse(g.source_ready())

    def test_arming_requires_source_quiet_configured_fresh_and_controls_released(self):
        for option in ('controls','deadline','source_active','source_disabled','stale'):
            g,clock,calls=self.make();neutral=True;elapsed=.6
            if option=='controls':neutral=False
            if option=='deadline':elapsed=100.001
            if option=='source_active':g.feed(frame(clock(),[event(1,600000,absolute())]))
            if option=='source_disabled':g.feed(frame(clock(),flags=3))
            if option=='stale':clock.now+=.081
            with self.assertRaises(BridgeFault):g.arm(neutral,elapsed)
            self.assertFalse(any(k=='send' for k,t in calls));self.assertIsNotNone(g.output.fault)

    def test_source_silence_window_and_manual_click_deadline(self):
        g,clock,calls=self.make();clock.now=.61;g.feed(frame(clock(),[event(1,610000,absolute())]))
        clock.now=.7;g.feed(frame(clock(),[event(2,700000,NEUTRAL)]));self.assertFalse(g.source_ready())
        clock.now=1.2;g.feed(frame(clock()));self.assertTrue(g.source_ready())
        s=dict(phase='INPUT_READY',clock='monotonic',deadline_monotonic=100,source_neutral_ready=True)
        self.assertTrue(can_click(s,79));self.assertFalse(can_click(s,80));self.assertFalse(can_click(dict(s,source_neutral_ready=False),79))
        self.assertFalse(can_click(dict(s,clock='perf_counter'),79));self.assertFalse(can_click(dict(s,deadline_monotonic=float('nan')),79))

    def test_prearm_multi_group_activity_is_not_hidden_by_neutral_last_sample(self):
        g,clock,calls=self.make();clock.now=.61
        raw=((2<<30)|(16<<23)|(64<<1)).to_bytes(4,'little')*2
        g.feed(frame(clock(),[event(1,610000,raw)]))
        self.assertEqual(g.output.renderer.decoders[0].output()['low_amplitude'],0.)
        clock.now=1.105;g.feed(frame(clock()));self.assertFalse(g.source_ready())
        clock.now=1.111;g.feed(frame(clock()));self.assertTrue(g.source_ready());self.assertEqual(calls,[])

    def test_complete_episode_drains_then_stops_once_and_never_rearms(self):
        g,clock,calls=self.complete();s=g.summary()
        self.assertEqual(s['active_ms'],[296,296]);self.assertEqual(s['pre_arm_output_frames'],0)
        self.assertEqual(s['muted_reason'],'single bilateral episode completed');self.assertTrue(s['output_stop_confirmed'])
        sent=[t for k,t in calls if k=='send'];stopped=[t for k,t in calls if k=='stop']
        self.assertEqual(len(stopped),1);self.assertGreaterEqual(stopped[0]-sent[-1],.008-1e-9)
        with self.assertRaises(BridgeFault):g.arm(True,1)
        self.assertEqual(sum(k=='enable' for k,t in calls),1)

    def test_after_mute_collection_and_input_scheduler_can_continue_ten_seconds(self):
        g,clock,calls=self.complete();before=g.output.frames;count=len(g.events)
        for n in range(200):
            clock.pause(.05);g.feed(frame(clock(),[event(count+n,round(clock()*1e6),absolute())]));g.tick()
        self.assertEqual(g.output.frames,before);self.assertEqual(len(g.events),count+200);self.assertIsNone(g.output.fault)
        g.feed(frame(clock(),flags=25));self.assertTrue(g.terminal);self.assertEqual(g.output.renderer.muted_reason,'single bilateral episode completed')

    def test_heartbeat_cancel_and_early_terminal_always_stop(self):
        for mode in ('heartbeat','cancel','terminal'):
            g,clock,calls=self.make();g.arm(True,.6)
            if mode=='heartbeat':clock.now+=.081;g.tick()
            elif mode=='cancel':g.fail('user cancelled')
            else:g.feed(frame(clock(),flags=25))
            self.assertIsNotNone(g.output.fault);self.assertTrue(g.output.summary()['output_stop_confirmed'])

    def test_late_dispatch_does_not_catchup(self):
        g,clock,calls=self.make();target=g.arm(True,.6);clock.now=target+.005;g.feed(frame(clock()));g.tick()
        self.assertIn('late',g.output.fault);self.assertFalse(any(k=='send' for k,t in calls))

    def test_heartbeat_fault_stops_output_but_later_archive_and_terminal_remain_available(self):
        g,clock,calls=self.make();g.arm(True,.6)
        clock.now+=.081;g.tick();fault=g.output.fault
        self.assertTrue(g.output.summary()['output_stop_confirmed'])
        sent=g.output.frames;count=len(g.events)
        for n in range(200):
            clock.pause(.05);g.feed(frame(clock(),[event(count+n,round(clock()*1e6),absolute())]));g.tick()
        g.feed(frame(clock(),flags=25))
        self.assertTrue(g.terminal);self.assertEqual(g.output.fault,fault)
        self.assertEqual(g.output.frames,sent);self.assertEqual(len(g.events),count+200)
        with self.assertRaises(BridgeFault):g.arm(True,11)

    def test_game_archive_exceeds_short_replay_capacity_but_still_has_hard_limit(self):
        g,clock,calls=self.make()
        for seq in range(1,2725):g.feed(frame(clock(),[event(seq,600000,NEUTRAL)]))
        self.assertEqual(len(g.events),2725);self.assertIsNone(g.output.fault)
        g.feed(frame(clock(),[event(2725,600000,NEUTRAL)]));self.assertIn('capacity',g.output.fault)

    def test_sequence_gap_and_bad_motor_word_are_not_silently_dropped(self):
        for item in (event(2,600000,NEUTRAL),event(1,600000,b'bad')):
            g,clock,calls=self.make();g.feed(frame(clock(),[item]));self.assertIsNotNone(g.output.fault)

    def child_report(self):
        g,clock,calls=self.complete();report=g.summary()
        report.update(status='PASSED_SWITCH_FIDELITY_CHILD_PENDING_FLASH_LOG',manual_armed=True,output_stop_confirmed=True,terminal_received=True,
            terminal_ack_replied=True,collector_ended=True,timer_released=True,terminal_observed=True,pre_arm_output_frames=0,muted_reason='single bilateral episode completed',
            host_flash_write=False,persistent_flydigi_commands=0,actual_switch_game=True,live_elapsed_seconds=120.,
            input_relay=dict(slot=0,last_pro_input='000000000880000880',reads_after_output_stop=100,nonneutral_reads_after_output_stop=2,last_nonneutral_at_pc_clock=11.,last_read_at_pc_clock=120.))
        report['transport_diagnostics']=dict(responses=100,poll_calls=101,recent=[dict(kind='frame')],observed_boot_ids=[7])
        return report

    def parent_report(self):
        p=self.plan
        return dict(status='PASSED_SWITCH_FIDELITY_PROGRAM_PENDING_FLASH_LOG',child=self.child_report(),child_exit=0,guardian_killed_child=False,
            runtime_disable_ack=True,configuration_unchanged=True,post_neutral_discovery_ready=True,host_flash_write=False,persistent_flydigi_commands=0,
            identity_matches=True,state_matches=True,ram_matches=dict(global_config=True,mapping=True,lighting=True,motors=True),
            flash_log_validation_pending=True,firmware_log_write_expected=True,
            firmware_preflight=dict(verified=True,firmware_sha256=p['firmware_sha256'],baseline_generation=22,installed_snapshot_sha256=p['expected_full_flash_sha256']),
            accepted_input_proof=dict(verified=True,firmware_sha256=p['firmware_sha256'],accepted_input_generation=p['accepted_input_generation'],source_hashes=p['accepted_input_source_hashes']),plan_sha256='bound-plan',pc_input_liveness=dict(status='PASSED_ORDERED_PC_INPUT_LIVENESS',manual_started=True,slot=0,motor_commands=0,configuration_commands=0,final_pro_input='000000000880000880',transitions=[dict(stage=i) for i in range(5)]))

    def test_child_requires_real_postmute_input_and_complete_continuation(self):
        c=self.child_report();self.assertTrue(game_child_passed(c))
        for key,value in dict(pre_arm_output_frames=1,output_fault='timeout',terminal_ack_replied=False,active_ms=[321,296],live_elapsed_seconds=10,
            output_lateness_seconds=[.005]*51,peak_code=13,output_stop_confirmed=False).items():
            altered=copy.deepcopy(c);altered[key]=value;self.assertFalse(game_child_passed(altered),key)
        for key,value in dict(nonneutral_reads_after_output_stop=0,last_nonneutral_at_pc_clock=10.4,last_read_at_pc_clock=14.9,last_pro_input='pressed').items():
            altered=copy.deepcopy(c);altered['input_relay'][key]=value
            if key=='last_read_at_pc_clock':altered['input_relay'][key]=c['stopped_at_pc_clock']+4.9
            if key=='last_nonneutral_at_pc_clock':altered['input_relay'][key]=c['stopped_at_pc_clock']+.4
            self.assertFalse(game_child_passed(altered),key)

    def test_parent_requires_verified_accepted_input_firmware_and_configuration(self):
        p=self.parent_report();self.assertTrue(game_parent_passed(p,self.plan))
        for key,value in dict(configuration_unchanged=False,post_neutral_discovery_ready=False,guardian_killed_child=True,accepted_input_proof={},pc_input_liveness={},host_flash_write=True).items():
            altered=copy.deepcopy(p);altered[key]=value;self.assertFalse(game_parent_passed(altered,self.plan),key)

    def test_independent_source_reference_matches_emitted_model_and_ignores_later_muted_activity(self):
        c=self.child_report();reference=source_reference(c)
        self.assertEqual(reference['active_ms'],c['active_ms']);self.assertEqual(reference['squared_code_sum'],c['squared_code_sum']);self.assertTrue(reference['final_samples_neutral'])
        c['events'].append(dict(sequence=len(c['events']),at_us=2000000,motors=absolute().hex(),flags=7))
        self.assertEqual(source_reference(c),reference)

    def test_independent_source_reference_refuses_invented_tail(self):
        c=self.child_report()
        for e in c['events']:
            if e['at_us']>=1000000:e['motors']=absolute().hex()
        with self.assertRaisesRegex(ValueError,'neutral ending'):source_reference(c)

    def test_final_capture_cannot_mix_trials_or_skip_human_feedback(self):
        p=self.parent_report();plan=self.plan
        newest=dict(generation=23,events=[dict(motors_hex=e['motors']) for e in p['child']['events']],crc_valid=True,complete=True,no_flash_marker=0,dropped_events=0,target_offset='0xe0000',stream_end='client_confirmed',reason='capture_deadline')
        cap=dict(status='V043_HOST_FLASH_READBACK_VERIFIED',checks=dict(full_readback_verified=True,outside_journal_unchanged=True),firmware_sha256=plan['firmware_sha256'],newest=newest)
        base=dict(newest=dict(generation=22),full_flash_sha256=plan['expected_full_flash_sha256'])
        result=assess(p,plan,cap,base,'bound-plan',True,True,True,True);self.assertTrue(all(result['checks'].values()))
        self.assertEqual(assess(p,plan,cap,base,'bound-plan')['status'],'INCOMPLETE')
        for key,value in dict(generation=24,events=[],crc_valid=False,stream_end='drain_timeout',dropped_events=1).items():
            altered=copy.deepcopy(cap);altered['newest'][key]=value
            self.assertEqual(assess(p,plan,altered,base,'bound-plan',True,True,True,True)['status'],'INCOMPLETE',key)
        altered=copy.deepcopy(p);altered['child']['squared_code_sum'][0]+=1
        mismatch=assess(altered,plan,cap,base,'bound-plan',True,True,True,True)
        self.assertFalse(mismatch['checks']['independent_source_reconstruction']);self.assertEqual(mismatch['status'],'INCOMPLETE')

if __name__=='__main__':unittest.main()
