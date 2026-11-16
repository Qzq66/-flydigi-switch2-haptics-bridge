"""Deterministic, source-bound A/B plan and injected playback policy; no hardware."""
import hashlib,json,math,pathlib,time
from haptic_fidelity_candidate import decode_timeline,reconstruct
ROOT=pathlib.Path(__file__).absolute().parents[1]

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def build_plan():
    report_path=ROOT/'docs/fidelity-candidate-20261024-verified/REPORT.json'
    evidence=json.loads(report_path.read_text(encoding='utf-8'))
    if not evidence['tests_passed'] or evidence['live_output_enabled'] or not evidence['io_guard']:raise ValueError('Verified offline candidate required')
    for name,sha in evidence['source_sha256'].items():
        if digest(ROOT/name)!=sha:raise ValueError('Candidate evidence source changed: '+name)
    stamp='20261024-132744';source=ROOT/'docs'/('WINDOWS_V043_GAME_RECHECK_'+stamp+'.json')
    p=json.loads(source.read_text(encoding='utf-8'));c=p['child']
    accepted=json.loads((ROOT/'docs'/('V043_DODGE_ATTACK_ASSESSMENT_'+stamp+'.json')).read_text())
    if accepted['journal_generation']!=18 or not all(accepted['checks'].values()) or not p['configuration_unchanged']:raise ValueError('Accepted single-event source required')
    anchor=c['source_clock_anchor'];arm=anchor['source_us']+(c['armed_at_pc_clock']-anchor['pc_clock'])*1e6
    timelines,_=decode_timeline(c['events'],arm)
    end=max(c['events'][-1]['at_us'],max(t[-1]['at_us'] for t in timelines))+2000
    rendered=reconstruct(timelines,arm,end,gain=96)
    ranges=[]
    for side in rendered['active']:
        indices=[n for n,active in enumerate(side) if active]
        if not indices or len(indices)!=indices[-1]-indices[0]+1:raise ValueError('Exactly one complete contiguous activity episode per grip required')
        ranges.append((indices[0],indices[-1]))
    first=max(0,min(a for a,b in ranges)-8);last=max(b for a,b in ranges)+9
    b_pcm=[side[first:last] for side in rendered['pcm']]
    while len(b_pcm[0])%8:
        for side in b_pcm:side.append(128)
    a_pcm=[[128+round(12*math.sin(2*math.pi*hz*n/1000)) for n in range(120)] for hz in (160,320)]
    segments=[dict(label='A',kind='fixed_notification',pcm=a_pcm),dict(label='B',kind='source_dual_band',pcm=b_pcm)]
    for segment in segments:
        segment['samples_per_side']=len(segment['pcm'][0])
        segment['peak_code']=max(abs(v-128) for side in segment['pcm'] for v in side)
        segment['squared_code_sum']=[sum((v-128)**2 for v in side) for side in segment['pcm']]
    if segments[1]['samples_per_side']>320:raise ValueError('B segment exceeds 320ms ceiling')
    total_samples=sum(s['samples_per_side'] for s in segments)
    doses=[sum(s['squared_code_sum'][side] for s in segments) for side in (0,1)]
    if total_samples>440 or any(n>20000 for n in doses) or any(s['peak_code']>12 for s in segments):raise ValueError('Finite comparison sample/dose bound exceeded')
    tool_names=('fidelity_ab_plan.py','run_fidelity_ab.py','fidelity_ab_window.py')
    return dict(version=1,source_trial=stamp,source_journal_generation=18,source_program_sha256=digest(source),
        reconstruction_report_sha256=digest(report_path),tool_sha256={name:digest(ROOT/'tools'/name) for name in tool_names},
        sample_rate_hz=1000,maximum_offset=12,gain_b=96,preparation_seconds=6,inter_segment_silence_seconds=5,
        arm_window_seconds=45,guardian_seconds=75,maximum_total_samples_per_side=440,maximum_squared_code_sum_per_side=20000,
        total_samples_per_side=total_samples,squared_code_sum_per_side=doses,b_source_sample_range=[first,last],
        b_source_activity_ms=[sum(side) for side in rendered['active']],segments=segments,
        persistent_flydigi_commands=0,pico_access=False,switch_access=False,
        scope='One PC-only A then B comparison, fixed prompt vs one complete captured dual-band episode. Numerical dose is not a thermal model or physical equivalence.')

def validate_plan(plan):
    if plan!=build_plan():raise ValueError('A/B plan differs from reviewed source-bound comparison')

def ab_child_succeeded(child,exit_code,plan,killed=False):
    if killed or exit_code!=0 or not isinstance(child,dict) or child.get('status')!='PASSED_FIDELITY_AB_CLIP_PROGRAM' or child.get('manual_armed') is not True or child.get('timer_released') is not True or child.get('error'):return False
    segments=child.get('segments',[])
    if len(segments)!=2:return False
    for segment,expected in zip(segments,plan['segments']):
        if segment.get('label')!=expected['label'] or segment.get('stop',{}).get('runtime_disable_ack') is not True:return False
        playback=segment.get('playback',{})
        if playback.get('samples_per_side')!=expected['samples_per_side'] or playback.get('frames')!=expected['samples_per_side']//8:return False
    accepted=child.get('manual_accepted_at_monotonic');a_start=segments[0].get('started_at_monotonic')
    a_stop=segments[0].get('stop',{}).get('confirmed_at_monotonic');b_start=segments[1].get('started_at_monotonic')
    if not all(type(v) in (int,float) and math.isfinite(v) for v in (accepted,a_start,a_stop,b_start)):return False
    return a_start-accepted>=6 and a_stop>=a_start and b_start-a_stop>=5

def play_segment(segment,enable,send,stop,clock=time.perf_counter,pause=time.sleep,cancelled=lambda:False):
    """Always stop, including enable/write/scheduler failure; never catch up."""
    left,right=segment['pcm'];frames=0
    if len(left)!=len(right) or not len(left) or len(left)%8 or len(left)>320:raise ValueError('Invalid bounded segment')
    if any(type(v) is not int or abs(v-128)>12 for v in left+right):raise ValueError('Invalid bounded sample')
    if cancelled():raise RuntimeError('Comparison cancelled before enable')
    try:
        enable();start=clock()
        for offset in range(0,len(left),8):
            if cancelled():raise RuntimeError('Comparison cancelled during output')
            target=start+offset/1000;now=clock()
            if now<target:pause(target-now)
            if cancelled():raise RuntimeError('Comparison cancelled before next block')
            if clock()>target+.016:raise RuntimeError('Scheduler late; no catch-up')
            send(left[offset:offset+8],right[offset:offset+8]);frames+=1
        # Do not cancel the final eight samples immediately after submitting them.
        pause(.008)
        return dict(frames=frames,samples_per_side=len(left),elapsed_seconds=clock()-start)
    finally:stop()
