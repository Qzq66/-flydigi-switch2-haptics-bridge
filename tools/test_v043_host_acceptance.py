"""Host evidence must distinguish full duration, safe early ends and broken data."""
import copy,unittest
from assess_v043_host import assess,NEUTRAL

def evidence():
    c=dict(status='PASSED_SWITCH_WIFI_INPUT_END_CHECK',ended_reason='terminal stream complete',terminal_received=True,terminal_ack_replied=True,
        collector_ended=True,timer_released=True,motor_output_enabled=False,output_frames=0,live_started_at_pc_clock=1000,live_elapsed_seconds=119.8,
        input_relay=dict(nonneutral_reads=20,last_pro_input=NEUTRAL.hex(),last_read_at_pc_clock=1119.5,last_nonneutral_at_pc_clock=1105),
        events=[dict(sequence=0,motors='0001404000014040')])
    p=dict(status='PASSED_V043_SWITCH_INPUT_END_PROGRAM_CHECKS',child=c,child_exit=0,runtime_disable_ack=True,configuration_unchanged=True,guardian_killed_child=False,
        firmware_preflight=dict(verified=True,variant='v043',baseline_generation=10))
    capture=dict(generation=11,no_flash_marker=0,target_offset='0xe0000',crc_valid=True,complete=True,dropped_events=0,stream_end='client_confirmed',reason='capture_deadline',elapsed_ms=121000,
        events=[dict(motors_hex='0001404000014040')])
    return p,capture,dict(generation=10)

class Acceptance(unittest.TestCase):
    def result(self,p,c,b,h=True):return assess(p,c,b,h)['status']
    def test_full_evidence_passes(self):self.assertEqual(self.result(*evidence()),'PASSED_V043_SWITCH_120S_INPUT_ACCEPTANCE')
    def test_capacity_and_boot_are_clean_but_not_full(self):
        for reason,label in (('capacity_limit','CAPACITY_LIMIT'),('boot_limit','BOOT_LIMIT')):
            p,c,b=evidence();c['reason']=reason;p['child']['live_elapsed_seconds']=35
            self.assertEqual(self.result(p,c,b),'CLEAN_EARLY_'+label)
    def test_short_deadline_never_passes(self):
        p,c,b=evidence();p['child']['live_elapsed_seconds']=59.8
        self.assertEqual(self.result(p,c,b),'INCOMPLETE_120S_ACCEPTANCE')
    def test_bad_integrity_is_not_clean_early(self):
        for key,value in (('complete',False),('crc_valid',False),('generation',10),('dropped_events',1),('stream_end','drain_timeout'),('events',[])):
            p,c,b=evidence();c.update(reason='capacity_limit');c[key]=value
            with self.subTest(key=key):self.assertEqual(self.result(p,c,b),'INCOMPLETE')
    def test_identity_required(self):
        for identity in ({},dict(verified=True,variant='v042',baseline_generation=10),dict(verified=True,variant='v043',baseline_generation=9)):
            p,c,b=evidence();p['firmware_preflight']=identity;self.assertEqual(self.result(p,c,b),'INCOMPLETE')
    def test_late_input_and_final_neutral_required(self):
        for key,value in (('last_pro_input','040000000880000880'),('last_read_at_pc_clock',1050),('last_nonneutral_at_pc_clock',1050)):
            p,c,b=evidence();p['child']['input_relay'][key]=value
            with self.subTest(key=key):self.assertEqual(self.result(p,c,b),'INCOMPLETE_120S_ACCEPTANCE')
    def test_human_confirmation_not_assumed(self):self.assertEqual(self.result(*evidence(),h=False),'INCOMPLETE_120S_ACCEPTANCE')
    def test_transport_pass_does_not_waive_late_manual_input(self):
        p,c,b=evidence();p['child']['input_relay']['last_nonneutral_at_pc_clock']=1073
        result=assess(p,c,b,True)
        self.assertTrue(result['transport_120s_validated']);self.assertEqual(result['pending_checks'],['late_nonneutral_observed'])
        self.assertEqual(result['status'],'INCOMPLETE_120S_ACCEPTANCE')
    def test_output_or_config_change_rejected(self):
        p,c,b=evidence();p['child']['output_frames']=1;self.assertEqual(self.result(p,c,b),'INCOMPLETE')
        p,c,b=evidence();p['configuration_unchanged']=False;self.assertEqual(self.result(p,c,b),'INCOMPLETE')

if __name__=='__main__':unittest.main()
