"""Fixed-frequency amplitude comparison; pure deterministic PCM plan."""
import json,math
from fidelity_ab_plan import ROOT,digest,play_segment,ab_child_succeeded

def tone(peak):
    if type(peak) is not int or peak not in (4,8):raise ValueError('Reviewed amplitude pair only')
    return [128+round(peak*math.sin(2*math.pi*160*n/1000)) for n in range(200)]+[128]*8

def build_plan():
    proof=ROOT/'docs/FREQUENCY_AB_ASSESSMENT_20261027-213455.json'
    evidence=json.loads(proof.read_text())
    if evidence['status']!='PASSED_CONTROLLED_FREQUENCY_COMPARISON_WITH_FEEDBACK' or not all(evidence['checks'].values()):raise ValueError('Complete frequency comparison required')
    frozen=ROOT/'docs/FREQUENCY_AB_RUN_FREEZE_20261027-213455.json'
    for row in json.loads(frozen.read_text())['files']:
        if digest(ROOT/row['path'])!=row['sha256']:raise ValueError('Frozen frequency evidence changed')
    segments=[]
    for label,peak in [('A',4),('B',8)]:
        pcm=tone(peak);dose=sum((v-128)**2 for v in pcm)
        segments.append(dict(label=label,kind='synthetic_single_tone',frequency_hz=160,active_duration_ms=200,neutral_tail_ms=8,
            pcm=[pcm,pcm.copy()],samples_per_side=len(pcm),peak_code=max(abs(v-128) for v in pcm),squared_code_sum=[dose,dose]))
    if not segments[0]['squared_code_sum'][0]<segments[1]['squared_code_sum'][0]:raise ValueError('Ordered digital amplitude required')
    total=sum(s['samples_per_side'] for s in segments);dose=[sum(s['squared_code_sum'][i] for s in segments) for i in (0,1)]
    if total>440 or any(v>20000 for v in dose) or any(s['peak_code']>8 or max(s['squared_code_sum'])>8000 for s in segments):raise ValueError('Conservative sample/dose bound exceeded')
    names=('amplitude_ab_plan.py','run_amplitude_ab.py','amplitude_ab_window.py','fidelity_ab_plan.py')
    return dict(version=1,comparison='amplitude_4_vs_8_fixed_160hz',sample_rate_hz=1000,maximum_offset=8,
        preparation_seconds=6,inter_segment_silence_seconds=5,arm_window_seconds=45,guardian_seconds=75,
        maximum_total_samples_per_side=440,maximum_squared_code_sum_per_side=20000,total_samples_per_side=total,
        squared_code_sum_per_side=dose,segments=segments,tool_sha256={n:digest(ROOT/'tools'/n) for n in names},
        frequency_evidence_sha256=digest(proof),frequency_freeze_sha256=digest(frozen),persistent_flydigi_commands=0,
        pico_access=False,switch_access=False,automatic_replay=False,
        scope='One fixed-160Hz synthetic amplitude comparison. Code amplitude is not Switch amplitude units or physical force; no native-fidelity or linear-force claim.')

def validate_plan(plan):
    if plan!=build_plan():raise ValueError('Amplitude plan or bound sources changed')
