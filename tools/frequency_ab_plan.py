"""Equal-duration and equal digital-dose frequency comparison; pure plan only."""
import json,math
from fidelity_ab_plan import ROOT,digest,play_segment,ab_child_succeeded

def tone(hz):
    if hz not in (80,240):raise ValueError('Reviewed comparison frequencies only')
    return [128+round(8*math.sin(2*math.pi*hz*n/1000)) for n in range(200)]+[128]*8

def build_plan():
    proof=ROOT/'docs/FIDELITY_GAME_REPEAT_ASSESSMENT_20261027-212240.json'
    evidence=json.loads(proof.read_text())
    if evidence['status']!='PASSED_TWO_INDEPENDENT_LIMITED_GAME_EPISODES' or not all(evidence['checks'].values()):raise ValueError('Two complete limited game episodes required')
    frozen=ROOT/'docs/FIDELITY_GAME_G40_RUN_FREEZE_20261027-212240.json'
    for row in json.loads(frozen.read_text())['files']:
        if digest(ROOT/row['path'])!=row['sha256']:raise ValueError('Frozen repeat source/evidence changed')
    segments=[]
    for label,hz in [('A',80),('B',240)]:
        pcm=tone(hz);dose=sum((v-128)**2 for v in pcm)
        segments.append(dict(label=label,kind='synthetic_single_tone',frequency_hz=hz,active_duration_ms=200,neutral_tail_ms=8,
            pcm=[pcm,pcm.copy()],samples_per_side=len(pcm),peak_code=max(abs(v-128) for v in pcm),squared_code_sum=[dose,dose]))
    if segments[0]['squared_code_sum']!=segments[1]['squared_code_sum']:raise ValueError('Digital dose must match exactly')
    total=sum(x['samples_per_side'] for x in segments);dose=[sum(x['squared_code_sum'][i] for x in segments) for i in (0,1)]
    if total>440 or any(x>20000 for x in dose) or any(x['peak_code']>8 or max(x['squared_code_sum'])>8000 for x in segments):raise ValueError('Existing conservative dose limits exceeded')
    names=('frequency_ab_plan.py','run_frequency_ab.py','frequency_ab_window.py','fidelity_ab_plan.py')
    return dict(version=1,comparison='frequency_80_vs_240_equal_digital_dose',sample_rate_hz=1000,maximum_offset=8,
        preparation_seconds=6,inter_segment_silence_seconds=5,arm_window_seconds=45,guardian_seconds=75,
        maximum_total_samples_per_side=440,maximum_squared_code_sum_per_side=20000,total_samples_per_side=total,
        squared_code_sum_per_side=dose,segments=segments,tool_sha256={n:digest(ROOT/'tools'/n) for n in names},
        repeat_evidence_sha256=digest(proof),repeat_freeze_sha256=digest(frozen),persistent_flydigi_commands=0,
        pico_access=False,switch_access=False,automatic_replay=False,
        scope='One synthetic frequency comparison. Equal quantised code energy is not equal physical force or mechanical energy; no native-fidelity claim.')

def validate_plan(plan):
    if plan!=build_plan():raise ValueError('Frequency plan or bound sources changed')
