"""Virtual-clock fault containment using an archived motor excerpt. No native I/O."""
import argparse,hashlib,json,pathlib,struct,sys,zlib
from archived_software_source import prepare,schedule
from software_replay_source import NEUTRAL
from sustained_game_session import SustainedGameSession
from dispatch_io_candidate import CandidateLoop
from bridge_protocol import unpack,BridgeFault
ROOT=pathlib.Path(__file__).resolve().parents[1]
CASES=('dispatch_stall','wire_gap','sequence_gap','output_error','collector_error')

def packet(now,events):
    stamp=round(now*1e6)
    body=struct.pack('<4sBBHQIIIHH',b'BHR2',2,7,36+16*len(events),1,42,99,stamp,len(events),0)
    body+=b''.join(struct.pack('<II8s',at,seq,raw) for at,seq,raw in events)
    result=unpack(body+struct.pack('<I',zlib.crc32(body)),1,42)
    result['received_at']=now
    return result

def run_case(events,case):
    if case not in CASES:raise ValueError('Unknown fault case')
    excerpt=prepare(events);now=[0.];enables=[];stops=[];attempts=[0];saw_active=[False];inject_writer=[False]
    def send(left,right):
        attempts[0]+=1
        if inject_writer[0]:raise OSError('Injected fake output failure')
        saw_active[0]=saw_active[0] or any(x!=128 for side in (left,right) for x in side)
    def stop():stops.append(now[0]);return dict(runtime_disable_ack=True)
    game=SustainedGameSession(lambda:enables.append(now[0]),send,stop,
        clock=lambda:now[0],pause=lambda seconds:now.__setitem__(0,now[0]+seconds))
    loop=CandidateLoop(game,lambda payload:None);sequence=0;raised=None;injected=False;gap_at=None;index=0
    try:
        for i in range(101):
            now[0]=i*.005
            loop.step([packet(now[0],[(round(now[0]*1e6),sequence,NEUTRAL)])]);sequence+=1
        game.arm(True,.5);rows=schedule(excerpt,game.output.renderer.armed_at,0)
        for _ in range(1500):
            now[0]=game.target
            trigger=saw_active[0] and not injected
            if trigger:
                injected=True
                if case=='dispatch_stall':now[0]+=.0087
                if case=='wire_gap':gap_at=now[0]
                if case=='output_error':inject_writer[0]=True
            batch=[]
            while index<len(rows) and rows[index][0]<=round(now[0]*1e6):
                at,raw=rows[index];batch.append((at,sequence,raw));sequence+=1;index+=1
            if trigger and case=='sequence_gap':
                batch.append((round(now[0]*1e6),sequence+1,NEUTRAL));sequence+=2
            frames=[] if gap_at is not None else [packet(now[0],batch)]
            if trigger and case=='collector_error':frames=[OSError('Injected fake collector failure')]
            try:loop.step(frames)
            except OSError as exc:raised=type(exc).__name__
            if game.output.fault:break
        first=loop.summary()['first_fault'];failure=game.summary();frozen_fault=failure['output_fault']
        frames_at_fault=failure['output_frames'];attempts_at_fault=attempts[0]
        for _ in range(3):
            now[0]+=.008;loop.step([packet(now[0],[])])
        rearm_rejected=False
        try:game.arm(True,now[0])
        except BridgeFault:rearm_rejected=True
        checks=dict(injected_during_real_excerpt_output=injected and saw_active[0],
            fault_latched=bool(frozen_fault) and game.output.fault==frozen_fault,
            first_fault_observed=first is not None,
            no_frame_in_fault_step=first is not None and first['frames_before']==first['frames_after'],
            no_postfault_output=game.output.frames==frames_at_fault and attempts[0]==attempts_at_fault,
            no_automatic_reenable=len(enables)==1,rearm_rejected=rearm_rejected,
            fake_stop_confirmed=failure['output_stop_confirmed'] is True,
            exactly_one_stop=len(stops)==1)
        expected={'dispatch_stall':'scheduler late','wire_gap':'heartbeat timeout','sequence_gap':'sequence gap','output_error':'fake output failure','collector_error':'Candidate loop error'}[case]
        checks['expected_fault_class']=expected in (frozen_fault or '')
        loop.close();checks['close_does_not_repeat_stop']=len(stops)==1
        checks['publisher_closed']=loop.publisher.summary()['closed'] and not loop.publisher.thread.is_alive()
        return dict(case=case,passed=all(checks.values()),checks=checks,fault=frozen_fault,
            frames_at_fault=frames_at_fault,writer_attempts=attempts[0],stop_calls=len(stops),
            first_fault=first,raised=raised,wire_gap_started=gap_at,
            maximum_output_lateness_seconds=.004,heartbeat_seconds=.080)
    finally:
        loop.close()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=pathlib.Path,default=ROOT/'docs/FIDELITY_GAME_RUN_20261115-165425.json')
    parser.add_argument('--output',type=pathlib.Path,required=True);args=parser.parse_args()
    if args.output.exists():raise ValueError('Evidence exists')
    def audit(event,values):
        if event.startswith('socket.') or event in ('subprocess.Popen','os.system','os.startfile','ctypes.dlopen','ctypes.call_function'):raise PermissionError(event)
    sys.addaudithook(audit);raw=args.source.read_bytes();source=json.loads(raw)['child']['events']
    results=[run_case(source,case) for case in CASES]
    report=dict(status='PASSED_INJECTED_FAULT_CONTAINMENT' if all(x['passed'] for x in results) else 'INCOMPLETE',
        hardware_actions=0,network_actions=0,virtual_clock=True,fake_output_and_stop=True,
        source_sha256=hashlib.sha256(raw).hexdigest(),results=results,
        scope='Protection containment under deliberately injected faults; not root-cause diagnosis or real scheduling/hardware reliability')
    with args.output.open('x',encoding='utf-8') as out:json.dump(report,out,indent=2);out.write('\n')
    print(json.dumps(dict(status=report['status'],cases=[dict(case=x['case'],passed=x['passed'],failed=[k for k,v in x['checks'].items() if not v]) for x in results]),indent=2))
    return 0 if all(x['passed'] for x in results) else 1

if __name__=='__main__':raise SystemExit(main())
