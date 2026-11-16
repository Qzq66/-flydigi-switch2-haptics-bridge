"""Offline accepted-game parameter audit; no sockets, device or replay I/O."""
import hashlib,heapq,json,pathlib,sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from haptic_fidelity_candidate import ZERO,KEYS,reconstruct
from switch_hd_decode import Decoder
from live_fidelity_candidate import LiveFidelityRenderer

TRIALS=[('20261026-232226','FIDELITY_GAME_G37_ASSESSMENT_20261026-232226.json','FIDELITY_GAME_G37_RUN_FREEZE_20261026-232226.json'),
        ('20261027-212240','FIDELITY_GAME_G40_ASSESSMENT_20261027-212240.json','FIDELITY_GAME_G40_RUN_FREEZE_20261027-212240.json')]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def emitted_timelines(child):
    anchor=child['source_clock_anchor'];start=anchor['source_us']+(child['armed_at_pc_clock']-anchor['pc_clock'])*1e6
    end=start+child['output_frames']*8000;dec=[Decoder(),Decoder()];timelines=[[],[]]
    for index,event in enumerate(child['events']):
        if event['sequence']!=index:raise ValueError('Source sequence gap')
        if event['at_us']>=end:break
        raw=bytes.fromhex(event['motors'])
        if len(raw)!=8:raise ValueError('Motor field length')
        for side in (0,1):
            for i,sample in enumerate(dec[side].decode(raw[side*4:side*4+4])['samples']):
                at=event['at_us']+i*5000
                if not start<=at<end:continue
                if not sample['state_complete']:raise ValueError('Incomplete source state')
                values={k:sample[k] for k in KEYS} if event['flags']&4 else dict(ZERO)
                timelines[side].append(dict(at_us=at,**values))
    if any(not side or side[-1]['low_amplitude'] or side[-1]['high_amplitude'] for side in timelines):raise ValueError('Real neutral ending missing')
    return timelines,start,end

def core_reference(timelines,start,frames):
    # Deliberately isolate oscillator/block generation from packet arrival.
    # This does not replay transport, enforce pending-queue arrival limits,
    # or observe actual historical HID writes.
    r=LiveFidelityRenderer();r.armed=True;r.armed_at=0.;r.output_start=0.;r.last_received=0.
    order=0
    for side,points in enumerate(timelines):
        for point in points:
            order+=1
            heapq.heappush(r.pending,((point['at_us']-start)/1e6,order,side,[point[k] for k in KEYS]))
    out=[[],[]]
    for index in range(frames):
        now=index*.008;r.last_received=now
        block=r.block(now,observed_at=now)
        if block is None:raise ValueError('Core muted before recorded frame count')
        for side in (0,1):out[side].extend(block[side])
    if r.muted_reason!='single bilateral episode completed':raise ValueError('Core did not reach the same terminal episode')
    return out

def audit_trial(tag,assessment_name,freeze_name):
    docs=ROOT/'docs';assessment=json.loads((docs/assessment_name).read_text())
    if assessment['status']!='PASSED_SINGLE_SWITCH_GAME_DUAL_BAND_CANDIDATE' or not all(assessment['checks'].values()):raise ValueError('Full game acceptance required')
    for row in json.loads((docs/freeze_name).read_text())['files']:
        if sha(ROOT/row['path'])!=row['sha256']:raise ValueError('Frozen evidence changed')
    source=docs/('FIDELITY_GAME_RUN_'+tag+'.json');report=json.loads(source.read_text());child=report['child']
    if sha(source)!=assessment['source_sha256']['program']:raise ValueError('Source report binding')
    timelines,start,end=emitted_timelines(child);ref=reconstruct(timelines,start,end)
    core=core_reference(timelines,start,child['output_frames'])
    if core!=ref['pcm']:raise ValueError('Streaming core and independent reconstruction differ')
    if [sum(a) for a in ref['active']]!=child['active_ms']:raise ValueError('Activity differs')
    if [sum((v-128)**2 for v in side) for side in ref['pcm']]!=child['squared_code_sum']:raise ValueError('Digital dose differs')
    sides=[]
    for side,points in enumerate(timelines):
        previous=None;changes=0;bands={}
        for point in points:
            values=tuple(point[k] for k in KEYS)
            if previous is not None and previous!=values:changes+=1
            previous=values
        for band in ('low','high'):
            active=[p for p in points if p[band+'_amplitude']>0]
            bands[band]=dict(active_frequency_levels_hz=sorted({p[band+'_hz'] for p in active}),
                active_amplitude_levels=sorted({p[band+'_amplitude'] for p in active}),
                maximum_individual_code_amplitude=96*max((p[band+'_amplitude'] for p in active),default=0))
        band_counts={'both':0,'low_only':0,'high_only':0,'neutral':0};index=0;values=ZERO
        intervals=[];on=None
        for n in range(ref['samples']):
            at=start+n*1000
            while index<len(points) and points[index]['at_us']<=at:values=points[index];index+=1
            low=values['low_amplitude']>0;high=values['high_amplitude']>0
            band_counts['both' if low and high else 'low_only' if low else 'high_only' if high else 'neutral']+=1
            if (low or high) and on is None:on=n
            if not (low or high) and on is not None:intervals.append(dict(start_ms=on,end_ms=n,duration_ms=n-on));on=None
        if on is not None:raise ValueError('Activity ends outside captured interval')
        bound=max(96*(p['low_amplitude']+p['high_amplitude']) for p in points)
        if bound>12:raise ValueError('Conservative gain bound breached')
        sides.append(dict(side='left' if side==0 else 'right',decoded_points=len(points),parameter_changes=changes,
            bands=bands,band_active_sample_counts=band_counts,active_intervals_ms=intervals,
            conservative_peak_bound=bound,headroom_to_12=12-bound,metrics=ref['sides'][side],
            offline_pcm_sha256=hashlib.sha256(bytes(ref['pcm'][side])).hexdigest()))
    return dict(trial=tag,source_report_sha256=sha(source),accepted_assessment_sha256=sha(docs/assessment_name),
        compared_pcm_samples_per_side=ref['samples'],streaming_core_equals_independent_pcm=True,
        historical_pcm_bytes_recorded=False,transport_replayed=False,gain=96,sample_rate_hz=1000,sides=sides)

def main():
    result=dict(status='PASSED_ACCEPTED_GAME_PARAMETER_AND_SOFTWARE_CORE_AUDIT',hardware_access=False,motor_commands=0,
        mapping_changed=False,trials=[audit_trial(*trial) for trial in TRIALS],
        limitations=['Compares mathematical reconstruction with isolated software core, not recorded historical HID PCM bytes.',
        'No transport scheduling replay, physical force measurement or original-controller equivalence.',
        'Source active samples that quantise to neutral are not classified as source-off or packet loss.'])
    p=ROOT/'docs/GAME_PARAMETER_AUDIT_2026-10-27.json'
    with p.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps(result,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
