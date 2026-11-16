"""Bounded streaming lifecycle with injected I/O; collector/input owned separately."""
import hashlib,json,math,pathlib,time
from fidelity_ab_plan import ROOT,validate_plan
from live_fidelity_candidate import LiveFidelityRenderer,BridgeFault
from switch_hd_decode import Decoder

# Exact previously reviewed 043 snapshot RAM UF2 (not the Flash BIN).
RAM_SHA='49acbba65eea98c1ec29a18e697c33f364111a0b2a224f56bb792067c1ce8c56'

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def validate_baseline_refresh(report):
    if (report.get('status')!='V043_FLASH_READY_VERIFIED' or report.get('previous_generation')!=20
        or report.get('baseline_generation')!=21 or report.get('firmware_sha256')!='3f7df3484644560548917013a66caac2c7f4b6a4307768fbf377e3fb4e751f50'
        or report.get('full_flash_sha256')!='5fdd8a5209872542626179c99d1a7f4b3ce17b06d4512fbf1b3fc2af416024d1'
        or any(report.get(k) is not True for k in ('outside_journal_unchanged','physical_full_readback_verified','remains_in_bootsel'))
        or report.get('flash_write') is not False or report.get('flydigi_access') is not False):
        raise ValueError('Only the independently readback-verified generation21 journal refresh is accepted')

def build_network_plan(baseline_report=None):
    ab_path=ROOT/'docs/FIDELITY_AB_PLAN_2026-10-24_V2.json';validate_plan(json.loads(ab_path.read_text()))
    source=ROOT/'docs/WINDOWS_V043_GAME_RECHECK_20261024-132744.json';p=json.loads(source.read_text());c=p['child']
    anchor=c['source_clock_anchor'];arm=anchor['source_us']+(c['armed_at_pc_clock']-anchor['pc_clock'])*1e6
    decoders=[Decoder(),Decoder()];active_indices=[]
    for index,event in enumerate(c['events']):
        raw=bytes.fromhex(event['motors'])
        for side in (0,1):
            for i,s in enumerate(decoders[side].decode(raw[side*4:side*4+4])['samples']):
                if event['at_us']+i*5000>=arm and (s['low_amplitude'] or s['high_amplitude']):active_indices.append(index)
    first,last=min(active_indices),max(active_indices)+1
    if last>=len(c['events']):raise ValueError('No neutral ending after selected activity')
    selected=c['events'][first:last+1];decoders=[Decoder(),Decoder()]
    for side in (0,1):
        if decoders[side].decode(bytes.fromhex(selected[0]['motors'])[side*4:side*4+4])['format']!='one_7bit':raise ValueError('First word must independently restore all state')
    for event in selected[1:]:
        for side in (0,1):decoders[side].decode(bytes.fromhex(event['motors'])[side*4:side*4+4])
    if any(d.output()['low_amplitude'] or d.output()['high_amplitude'] for d in decoders):raise ValueError('Selected source does not end neutral')
    origin=selected[0]['at_us'];events=[dict(at_us=e['at_us']-origin,motors=e['motors']) for e in selected]
    if not 100000<=events[-1]['at_us']<=320000:raise ValueError('Source clip duration outside reviewed short window')
    names=('fidelity_network_session.py','fidelity_network_io.py','run_fidelity_network.py','fidelity_network_window.py','live_fidelity_candidate.py','pico_v043_probe.py','read_hotspot_state.ps1','v043_installation.py')
    plan=dict(version=3,source_trial='20261024-132744',source_program_sha256=digest(source),ab_plan_sha256=digest(ab_path),
        events=events,ram_uf2_sha256=RAM_SHA,expected_flash_generation=20,
        expected_full_flash_sha256='a34c9bc453c3946549fb0ec12ffe4c83a390e73933aae07c40038f089506f798',
        tool_sha256={name:digest(ROOT/'tools'/name) for name in names},
        arm_window_seconds=45,preparation_seconds=6,parent_guardian_seconds=140,postmute_input_seconds=.25,
        bootsel_enumeration_wait_seconds=30,
        maximum_injection_lateness_seconds=.004,maximum_output_lateness_seconds=.004,output_mode='one captured bilateral dual-band episode',flash_write=False,
        usb_injection='independent one-shot worker; joined before Pico reads or reset',reset_gate='exact immutable SNAP043 marker after END2; wait for BOOTSEL and compare full Flash',
        limits=dict(gain=96,maximum_offset=12,active_ms_per_side=320,squared_code_sum_per_side=8000,armed_seconds=15),
        scope='PC USB injection -> exact SRAM-only Pico043 -> real UDP -> streaming renderer -> Flydigi. Not current Switch game traffic.')
    if baseline_report is not None:
        path=ROOT/baseline_report
        if path.resolve().parent!=(ROOT/'docs').resolve() or path.suffix!='.json':raise ValueError('Public baseline attestation must be directly in docs')
        report=json.loads(path.read_text());validate_baseline_refresh(report)
        plan.update(expected_flash_generation=report['baseline_generation'],expected_full_flash_sha256=report['full_flash_sha256'],
            baseline_refresh=dict(path=path.relative_to(ROOT).as_posix(),sha256=digest(path)))
    return plan

def validate_network_plan(plan):
    refresh=plan.get('baseline_refresh')
    if plan!=build_network_plan(refresh['path'] if refresh else None):raise ValueError('Network replay plan or bound source changed')

def child_succeeded(c,plan):
    """Independently check evidence, never accept a status string on its own."""
    try:
        fields=[e['motors'] for e in plan['events']];prefix=c['initial_motor_fields']
        dec=[Decoder(),Decoder()]
        if not prefix or len(prefix)>16:return False
        for raw in prefix:
            value=bytes.fromhex(raw)
            if len(value)!=8:return False
            for side in (0,1):
                for s in dec[side].decode(value[side*4:side*4+4])['samples']:
                    if s['low_amplitude'] or s['high_amplitude']:return False
        events=c['events'];late=c['injection_lateness_seconds'];outlate=c['output_lateness_seconds']
        bounded=lambda values,limit:len(values)==2 and all(type(v) in (int,float) and math.isfinite(v) and 0<=v<=limit for v in values)
        return (c['status']=='PASSED_RAM_WIFI_FIDELITY_REPLAY_CHILD'
            and all(c.get(k) is True for k in ('manual_armed','output_stop_confirmed','terminal_received','terminal_ack_replied','collector_ended','timer_released','pico_ram_reset_requested','snapshot_phase_confirmed','injector_done','injector_joined','all_motor_fields_exact','sequence_contiguous'))
            and all(not c.get(k) for k in ('error','output_fault','cleanup_error','pico_reset_error','finalization_errors','injector_error','injector_cancelled'))
            and c.get('flash_write') is False and c.get('actual_switch_game') is False and c.get('persistent_flydigi_commands')==0
            and c['sent_motor_fields']==fields and [e['motors'] for e in events]==prefix+fields
            and [e['sequence'] for e in events]==list(range(len(events)))
            and c['muted_reason']=='single bilateral episode completed'
            and bounded(c['active_ms'],320) and min(c['active_ms'])>=100
            and bounded(c['squared_code_sum'],8000) and min(c['squared_code_sum'])>0
            and 0<c['peak_code']<=12 and 0<c['output_frames']<=1900
            and len(late)==len(fields) and all(math.isfinite(v) and 0<=v<=plan['maximum_injection_lateness_seconds'] for v in late)
            and len(outlate)==c['output_frames'] and all(math.isfinite(v) and 0<=v<=plan['maximum_output_lateness_seconds'] for v in outlate)
            and len(c['injection_write_seconds'])==len(fields) and all(math.isfinite(v) and 0<=v<=.080 for v in c['injection_write_seconds'])
            and len(c['output_write_seconds'])==c['output_frames'] and all(math.isfinite(v) and 0<=v<=.080 for v in c['output_write_seconds'])
            and c['input_calls_after_output_stop']>=5 and math.isfinite(c['input_time_after_output_stop']) and c['input_time_after_output_stop']>=.20
            and c['pico_input_updates_after_output_stop']>0)
    except (KeyError,ValueError,TypeError,IndexError,OverflowError):return False

def program_succeeded(report,plan):
    try:
        before=report['flash_before']
        return (report['child_exit']==0 and report['guardian_killed_child'] is False
            and child_succeeded(report['child'],plan)
            and all(report.get(k) is True for k in ('runtime_disable_ack','configuration_unchanged','full_flash_after_matches'))
            and before['verified'] is True and before['baseline_generation']==plan['expected_flash_generation']
            and before['installed_snapshot_sha256']==plan['expected_full_flash_sha256']
            and report.get('flash_write') is False and report.get('actual_switch_game') is False
            and report.get('automatic_resume') is False and report.get('persistent_flydigi_commands')==0
            and report.get('ram_image_sha256')==plan['ram_uf2_sha256']
            and not any(report.get(k) for k in ('error','cleanup_error','flash_cleanup_error')))
    except (KeyError,TypeError):return False

class StreamSession:
    def __init__(self,enable,send,stop,clock=time.perf_counter,pause=time.sleep):
        self.renderer=LiveFidelityRenderer();self.enable=enable;self.send=send;self.stop_output=stop;self.clock=clock;self.pause=pause
        self.dirty=False;self.fault=None;self.cleanup_error=None;self.stops=[];self.events=[];self.frames=0;self.last_sent=None;self.stopped_at=None
    def stop(self,drain=False):
        if not self.dirty:return
        if drain and self.last_sent is not None:
            left=.008-(self.clock()-self.last_sent)
            if left>0:self.pause(left)
        try:
            result=self.stop_output()
            if not isinstance(result,dict) or result.get('runtime_disable_ack') is not True:raise BridgeFault('Output stop unconfirmed')
            self.stops.append(result);self.dirty=False;self.stopped_at=self.clock()
        except BaseException as exc:
            self.cleanup_error=repr(exc);raise
    def abort(self,exc):
        if self.fault is None:self.fault=repr(exc)
        self.stop()
    def feed(self,frame):
        incoming=[dict(sequence=e['sequence'],at_us=e['at_us'],motors=e['motors'].hex()) for e in frame['events']]
        room=max(0,256-len(self.events));self.events.extend(incoming[:room])
        if len(incoming)>room:
            self.abort(BridgeFault('Bounded replay event capacity'));return
        if self.fault:return
        try:self.renderer.feed(frame)
        except BaseException as exc:self.abort(exc)
    def arm(self):
        if self.fault:raise BridgeFault('Cannot arm failed session')
        self.dirty=True
        try:
            self.enable();return self.renderer.arm(self.clock())
        except BaseException as exc:self.abort(exc);raise
    def tick(self,target):
        if self.fault:return None
        try:
            samples=self.renderer.block(target,observed_at=self.clock())
            if samples is None:
                self.stop(drain=True);return None
            if self.renderer.armed:
                self.send(*samples);self.frames+=1;self.last_sent=self.clock()
            return samples
        except BaseException as exc:self.abort(exc);return None
    def summary(self):
        return dict(output_fault=self.fault,cleanup_error=self.cleanup_error,output_frames=self.frames,output_stop_confirmed=bool(self.stops) and not self.dirty,
            active_ms=self.renderer.active_total,peak_code=self.renderer.maximum_offset,squared_code_sum=self.renderer.dose,
            muted_reason=self.renderer.muted_reason,stopped_at_pc_clock=self.stopped_at,events=self.events)
