"""A no-actuator transport/journal diagnostic, separate from game rendering."""
import json,math
from fidelity_game_policy import ROOT,digest,validate_game_plan

def build_plan():
    prerequisite=ROOT/'docs/FIDELITY_GAME_PLAN_2026-10-25_G22_DIAGNOSTIC.json'
    game=json.loads(prerequisite.read_text());validate_game_plan(game)
    names=('passive_transport_policy.py','run_passive_transport.py','game_transport_diagnostics.py','game_input_liveness.py')
    return dict(version=1,kind='no_actuator_transport_and_journal_diagnostic',
        prerequisite_plan_sha256=digest(prerequisite),expected_flash_generation=game['expected_flash_generation'],
        expected_full_flash_sha256=game['expected_full_flash_sha256'],firmware_sha256=game['firmware_sha256'],
        source_sha256={n:digest(ROOT/'tools'/n) for n in names},
        host_seconds=123,discovery_seconds=120,guardian_seconds=270,maximum_events=2725,
        motor_commands=0,persistent_configuration_commands=0,input_forwarding='fixed_neutral',
        heartbeat_observation_seconds=.080,automatic_reconnect=False,host_flash_write=False,
        firmware_log_write_expected=True)

def validate_plan(plan):
    if plan!=build_plan():raise ValueError('Passive plan or bound sources changed')

class PassiveSession:
    def __init__(self):
        self.events=[];self.last_received=None;self.last_source=None;self.terminal=False
        self.flags=0;self.gaps=[];self.gap_active=False;self.upstream_seen=False

    def feed(self,frame):
        now=frame['received_at']
        if not math.isfinite(now) or self.last_received is not None and now<self.last_received:raise ValueError('Receiver clock reversed')
        stamp=frame['source_us']
        if self.last_source is not None and ((stamp-self.last_source+0x80000000)&0xffffffff)-0x80000000<0:raise ValueError('Source clock reversed')
        self.last_source=stamp;self.last_received=now;self.gap_active=False
        self.flags=frame['flags'];self.upstream_seen|=bool(self.flags&2)
        for e in frame['events']:
            if len(self.events)>=2725 or e['sequence']!=len(self.events) or len(e['motors'])!=8:raise ValueError('Archive capacity, sequence or motor field')
            self.events.append(dict(sequence=e['sequence'],at_us=e['at_us'],motors=e['motors'].hex(),flags=self.flags))
        self.terminal|=bool(self.flags&16)

    def tick(self,now):
        if self.last_received is not None and now-self.last_received>.080 and not self.gap_active:
            self.gap_active=True
            if len(self.gaps)<64:self.gaps.append(dict(observed_at=now,last_received=self.last_received))

    def summary(self):
        return dict(events=self.events,heartbeat_gap_observations=self.gaps,terminal_observed=self.terminal,
            upstream_seen=self.upstream_seen,motor_commands=0,output_frames=0)

def collection_completed(report):
    return (report.get('motor_commands')==0 and report.get('output_frames')==0
        and report.get('terminal_observed') is True and report.get('terminal_ack_replied') is True
        and report.get('collector_ended') is True and report.get('timer_released') is True
        and 110<=report.get('live_elapsed_seconds',0)<=124
        and bool(report.get('events')) and not report.get('error') and not report.get('finalization_errors'))
