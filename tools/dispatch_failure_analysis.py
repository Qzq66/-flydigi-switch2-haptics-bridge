"""Pure analysis and synthetic fault injection; no hardware or networking."""
from sustained_game_session import SustainedGameSession
NEUTRAL=bytes.fromhex('0001404000014040')
def frame(now,events=()):return dict(received_at=now,processed_at=now,source_us=round(now*1e6),events=list(events),flags=7)
def event(seq,at,raw):return dict(sequence=seq,at_us=at,motors=raw)


def inject_delay(kind,delay):
    now=[0.];calls=[];seq=0
    def send(left,right):
        calls.append('frame')
        if kind=='writer_block':now[0]+=delay
    s=SustainedGameSession(lambda:calls.append('enable'),send,lambda:(calls.append('stop') or dict(runtime_disable_ack=True)),lambda:now[0],lambda n:now.__setitem__(0,now[0]+n))
    for i in range(101):
        now[0]=i*.005;s.feed(frame(now[0],[event(seq,round(now[0]*1e6),NEUTRAL)]));seq+=1
    s.arm(True,.5);now[0]=s.target;s.feed(frame(now[0]))
    if kind=='writer_block':
        s.tick();s.feed(frame(now[0]));s.tick()
    else:
        now[0]+=delay;s.tick()
    return dict(kind=kind,injected_seconds=delay,fault=s.output.fault,frames=s.output.frames,stops=calls.count('stop'),mode_enables=calls.count('enable'),output_dirty=s.output.dirty,heartbeat_age_seconds=now[0]-s.output.renderer.last_received)


def analyse(program):
    c=program['child'];armed=c['armed_at_pc_clock'];frames=c['output_frames'];target=armed+.064+frames*.008
    result=dict(first_fault=c['output_fault'],submitted_frames=frames,rendered_timeline_seconds=frames*.008,
        next_dispatch_target_pc_clock=target,late_fault_strict_lower_bound_pc_clock=target+.004,
        stop_confirmation_pc_clock=c['stopped_at_pc_clock'],exact_failure_lateness_not_recorded=True,
        maximum_successful_dispatch_lateness_ms=max(c['output_lateness_seconds'])*1000,
        maximum_successful_writer_ms=max(c['output_write_seconds'])*1000,
        maximum_receive_gap_at_fault_ms=c['transport_at_output_fault']['maximum_response_gap_seconds']*1000,
        root_cause='unproven',phase_order=['unbounded inbox drain','possible synchronous phase-file write','game.tick deadline check','sleep1ms'])
    result['checks']=dict(dispatch_fault=c['output_fault']=="BridgeFault('Game PCM scheduler late; no catch-up')",not_heartbeat_fault='heartbeat' not in c['output_fault'],recorded_receive_gaps_within80ms=result['maximum_receive_gap_at_fault_ms']<80,stop_confirmed=c['output_stop_confirmed'] is True,configuration_unchanged=program['configuration_unchanged'] is True,no_rearm=not c.get('automatic_fault_recovery'))
    return result
