"""Independent one-episode Switch game candidate; no device or socket access."""
import json,math,time
from fidelity_network_session import ROOT,digest,StreamSession,program_succeeded as network_passed
from live_fidelity_candidate import BridgeFault
from bridge_input import NEUTRAL
from switch_hd_decode import Decoder

def build_game_plan():
    docs=ROOT/'docs';program=docs/'FIDELITY_NETWORK_RUN_20261025-143749.json';assessment=docs/'FIDELITY_NETWORK_ASSESSMENT_20261025-143749.json'
    network_plan=docs/'FIDELITY_NETWORK_PLAN_2026-10-25_V3.json';p=json.loads(program.read_text());a=json.loads(assessment.read_text());n=json.loads(network_plan.read_text())
    if not network_passed(p,n) or a['status']!='PASSED_CAPTURED_WIFI_DUAL_BAND_FULL_AUTOMATIC_RECOVERY_AND_HUMAN' or not all(a['checks'].values()):raise ValueError('Full automatic V3 replay and human acceptance required')
    for name,h in a['source_sha256'].items():
        if digest(docs/name)!=h:raise ValueError('Replay evidence changed')
    for name,h in n['tool_sha256'].items():
        if digest(ROOT/'tools'/name)!=h:raise ValueError('Successful V3 source changed')
    from v043_game_gate import authorize
    proof=authorize(docs/'V043_STAGED_GAME_PREREQUISITE_20261023.json',p['flash_before'])
    names=('fidelity_game_policy.py','run_fidelity_game.py','fidelity_game_window.py','assess_fidelity_game.py','haptic_fidelity_candidate.py','fidelity_network_session.py','live_fidelity_candidate.py','v043_game_gate.py','assess_v043_host.py','listener_readiness.py','v043_installation.py','collect_v043_host.py','game_input_liveness.py','game_transport_diagnostics.py')
    old=('bridge-switch-live.py','bridge_transport.py','bridge_render.py','bridge_windows.py','bridge_protocol.py','bridge_session_policy.py','bridge_process.py','bridge_input.py','bridge_network.py','bridge_runtime.py','switch_hd_decode.py')
    frozen={item['path']:item['sha256'] for item in json.loads((docs/'FIDELITY_AB_BASELINE_2026-10-24.json').read_text())['files']}
    for name in old:
        relative='handoff/2026-10-22/work/'+name
        if digest(ROOT/relative)!=frozen[relative]:raise ValueError('Accepted input/transport source changed: '+name)
    baseline_path=docs/'V043_READY_BASELINE_20261025-151716.json';baseline=json.loads(baseline_path.read_text())
    if (baseline['status']!='V043_FLASH_READY_VERIFIED' or baseline['baseline_generation']!=22 or baseline['physical_full_readback_verified'] is not True or baseline['outside_journal_unchanged'] is not True or baseline['firmware_sha256']!=p['flash_before']['firmware_sha256']):raise ValueError('Verified generation-22 baseline required')
    return dict(version=3,collect_after_output_fault=True,transport_diagnostics_required=True,scene='dodge-attack',pc_input_liveness_required=True,baseline_proof_sha256=digest(baseline_path),expected_flash_generation=22,expected_full_flash_sha256=baseline['full_flash_sha256'],firmware_sha256=p['flash_before']['firmware_sha256'],
        tool_sha256={name:digest(ROOT/'tools'/name) for name in names},transport_sha256={name:digest(ROOT/'handoff/2026-10-22/work'/name) for name in old},
        prerequisite_sha256={name.name:digest(name) for name in (program,assessment,network_plan,docs/'V043_STAGED_GAME_PREREQUISITE_20261023.json')},accepted_input_generation=proof['accepted_input_generation'],accepted_input_source_hashes=proof['source_hashes'],
        live_seconds=120,host_seconds=122,discovery_seconds=120,guardian_seconds=270,arm_latest_seconds=100,ui_arm_reserve_seconds=20,
        limits=dict(maximum_events=2725,gain=96,maximum_offset=12,maximum_active_ms_per_side=320,maximum_squared_code_sum_per_side=8000,maximum_armed_seconds=15,maximum_output_lateness_seconds=.004,heartbeat_seconds=.080),
        manual_click_required=True,host_flash_write=False,firmware_log_write_expected=True,automatic_replay=False,
        scope='One live Switch game episode, independent candidate; pending physical journal readback and human feedback after every hardware attempt.')

def validate_game_plan(plan):
    if plan!=build_game_plan():raise ValueError('Game plan or prerequisite source changed')

class GameSession:
    """Own source archive independently of the 256-event short replay wrapper."""
    def __init__(self,enable,send,stop,clock=time.perf_counter,pause=time.sleep):
        self.output=StreamSession(enable,send,stop,clock,pause);self.clock=clock
        self.events=[];self.latest_flags=0;self.first_received=None;self.last_active=None;self.terminal=False
        self.target=None;self.arm_attempted=False;self.pre_arm_frames=None;self.output_lateness=[];self.output_write_seconds=[]
        self.quiet_decoders=[Decoder(),Decoder()]

    def fail(self,why):self.output.abort(BridgeFault(why))

    def feed(self,frame):
        self.latest_flags=frame['flags']
        if self.first_received is None:self.first_received=frame['received_at']
        for event in frame['events']:
            if len(self.events)>=2725:self.fail('Game archive capacity');return
            if event['sequence']!=len(self.events):self.fail('Game archive sequence gap');return
            if len(event['motors'])!=8:self.fail('Invalid game motor field');return
            self.events.append(dict(sequence=event['sequence'],at_us=event['at_us'],motors=event['motors'].hex(),flags=frame['flags']))
            if not self.output.renderer.armed:
                for side in (0,1):
                    for i,sample in enumerate(self.quiet_decoders[side].decode(event['motors'][side*4:side*4+4])['samples']):
                        if not sample['state_complete'] or sample['low_amplitude'] or sample['high_amplitude']:
                            at=frame['received_at']+i*.005;self.last_active=at if self.last_active is None else max(at,self.last_active)
        if frame['flags']&16:self.terminal=True
        if self.output.fault:return
        try:
            self.output.renderer.feed(frame)
            if not self.output.renderer.armed:
                values=[d.output() for d in self.output.renderer.decoders]
                if any(not v['state_complete'] or v['low_amplitude'] or v['high_amplitude'] for v in values):self.last_active=max(self.last_active or 0,frame['received_at'])
            if frame['flags']&8 and self.output.dirty:
                self.fail('Upstream ended before complete game episode')
        except BaseException as exc:self.output.abort(exc)

    def arm(self,controls_neutral,live_elapsed):
        if self.arm_attempted or self.output.fault:raise BridgeFault('Game arm is one-shot')
        self.arm_attempted=True;now=self.clock()
        if not controls_neutral or not 0<=live_elapsed<=100:self.fail('Controls or game arming deadline');raise BridgeFault('Controls or game arming deadline')
        quiet=self.last_active if self.last_active is not None else self.first_received
        values=[d.output() for d in self.output.renderer.decoders]
        if (self.latest_flags&6!=6 or not self.events or quiet is None or now-quiet<.5
            or any(not v['state_complete'] or v['low_amplitude'] or v['high_amplitude'] for v in values)):
            self.fail('Require configured neutral source quiet for 500ms');raise BridgeFault('Require configured neutral source quiet for 500ms')
        self.pre_arm_frames=self.output.frames
        if self.pre_arm_frames!=0:self.fail('Pre-arm output was not silent');raise BridgeFault('Pre-arm output was not silent')
        self.target=self.output.arm();return self.target

    def source_ready(self):
        now=self.clock();r=self.output.renderer;quiet=self.last_active if self.last_active is not None else self.first_received
        values=[d.output() for d in r.decoders]
        return (not self.output.fault and not r.armed and self.latest_flags&6==6 and bool(self.events) and quiet is not None and now-quiet>=.5
            and r.last_received is not None and 0<=now-r.last_received<=.080
            and all(v['state_complete'] and not(v['low_amplitude'] or v['high_amplitude']) for v in values))

    def tick(self):
        if self.output.fault or self.terminal:return
        r=self.output.renderer;now=self.clock()
        if self.latest_flags&8:return
        try:
            if not r.armed or not self.output.dirty:
                r.block(now,observed_at=now);return
            if now<self.target:return
            if now-self.target>.004:self.fail('Game PCM scheduler late; no catch-up');return
            started=now;before=self.output.frames;self.output.tick(self.target)
            if self.output.frames>before:
                self.output_lateness.append(started-self.target);self.output_write_seconds.append(self.clock()-started)
            self.target+=.008
        except BaseException as exc:self.output.abort(exc)

    def summary(self):
        r=self.output.renderer;result=self.output.summary();result['events']=self.events
        result.update(manual_armed=r.armed,pre_arm_output_frames=self.pre_arm_frames,source_clock_anchor=dict(source_us=r.anchor[0],pc_clock=r.anchor[1]) if r.anchor else None,
            armed_at_pc_clock=r.armed_at,output_lateness_seconds=self.output_lateness,output_write_seconds=self.output_write_seconds,terminal_observed=self.terminal)
        return result

def game_child_passed(c):
    try:
        if not all(c.get(k) is True for k in ('manual_armed','output_stop_confirmed','terminal_received','terminal_ack_replied','collector_ended','timer_released','terminal_observed')):return False
        if any(c.get(k) for k in ('error','output_fault','cleanup_error','finalization_errors')):return False
        if c['pre_arm_output_frames']!=0 or c['muted_reason']!='single bilateral episode completed':return False
        if c.get('host_flash_write') is not False or c.get('persistent_flydigi_commands')!=0 or c.get('actual_switch_game') is not True:return False
        for values,limit in ((c['active_ms'],320),(c['squared_code_sum'],8000)):
            if len(values)!=2 or not all(type(v) in (int,float) and math.isfinite(v) and 0<v<=limit for v in values):return False
        late=c['output_lateness_seconds'];writes=c['output_write_seconds'];events=c['events'];relay=c['input_relay']
        diagnostics=c['transport_diagnostics']
        if (diagnostics['responses']<=0 or diagnostics['poll_calls']<diagnostics['responses']
            or not diagnostics['recent'] or len(diagnostics['observed_boot_ids'])!=1):return False
        return (0<c['peak_code']<=12 and 0<c['output_frames']<=1900 and len(late)==len(writes)==c['output_frames']
            and all(math.isfinite(v) and 0<=v<=.004 for v in late) and all(math.isfinite(v) and 0<=v<=.080 for v in writes)
            and 0<len(events)<=2725 and [e['sequence'] for e in events]==list(range(len(events)))
            and relay['last_pro_input']==NEUTRAL.hex() and relay['reads_after_output_stop']>=5
            and relay['nonneutral_reads_after_output_stop']>0 and relay['last_nonneutral_at_pc_clock']>c['stopped_at_pc_clock']+.5
            and relay['last_read_at_pc_clock']>=c['stopped_at_pc_clock']+5
            and 110<=c['live_elapsed_seconds']<=123 and c['status']=='PASSED_SWITCH_FIDELITY_CHILD_PENDING_FLASH_LOG')
    except (KeyError,TypeError,ValueError,OverflowError):return False

def game_parent_passed(p,plan):
    try:
        from game_input_liveness import passed as liveness_passed
        f=p['firmware_preflight'];proof=p['accepted_input_proof']
        if not liveness_passed(p.get('pc_input_liveness',{})) or p['child']['input_relay']['slot']!=p['pc_input_liveness']['slot']:return False
        return (game_child_passed(p['child']) and p['child_exit']==0 and p['guardian_killed_child'] is False
            and all(p.get(k) is True for k in ('runtime_disable_ack','configuration_unchanged','post_neutral_discovery_ready'))
            and p.get('identity_matches') is True and p.get('state_matches') is True and len(p.get('ram_matches',{}))==4 and all(p['ram_matches'].values())
            and not any(p.get(k) for k in ('error','cleanup_error')) and f['verified'] is True
            and f['firmware_sha256']==plan['firmware_sha256'] and f['baseline_generation']==plan['expected_flash_generation']
            and f['installed_snapshot_sha256']==plan['expected_full_flash_sha256']
            and proof['verified'] is True and proof['firmware_sha256']==f['firmware_sha256'] and proof['accepted_input_generation']==plan['accepted_input_generation']
            and proof.get('source_hashes')==plan['accepted_input_source_hashes']
            and p['host_flash_write'] is False and p['persistent_flydigi_commands']==0
            and p.get('flash_log_validation_pending') is True and p.get('firmware_log_write_expected') is True)
    except (KeyError,TypeError):return False

def can_click(status,now):
    d=status.get('deadline_monotonic')
    return (status.get('clock')=='monotonic' and status.get('phase')=='INPUT_READY' and status.get('source_neutral_ready') is True
        and type(d) in (float,int) and math.isfinite(d) and math.isfinite(now) and d-now>20)
