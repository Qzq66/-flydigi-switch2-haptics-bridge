# SPDX-License-Identifier: GPL-2.0-only
"""Offline-only dual-band reconstruction; intentionally has no hardware adapter."""
import math,pathlib,sys
sys.path.insert(0,str(pathlib.Path(__file__).absolute().parents[1]/'handoff/2026-10-22/work'))
from switch_hd_decode import Decoder

ZERO=dict(low_amplitude=0.,low_hz=160.,high_amplitude=0.,high_hz=320.)
KEYS=tuple(ZERO)

def decode_timeline(events,arm_source):
    decoders=[Decoder(),Decoder()];sides=[[],[]];prefix_conflicts=[0,0];previous=[None,None]
    for sequence,event in enumerate(events):
        if event['sequence']!=sequence:raise ValueError('Missing source sequence')
        raw=bytes.fromhex(event['motors'])
        if len(raw)!=8:raise ValueError('Exactly two motor words required')
        for side,decoder in enumerate(decoders):
            decoded=decoder.decode(raw[side*4:side*4+4])
            if event['at_us']>=arm_source and not event['flags']&4:
                sides[side].append(dict(at_us=event['at_us'],**ZERO));continue
            for i,sample in enumerate(decoded['samples']):
                at=event['at_us']+5000*i
                if at<arm_source:
                    if previous[side] is not None and at<previous[side]:prefix_conflicts[side]+=1
                    previous[side]=at;continue
                if not sample['state_complete']:raise ValueError('Unknown post-arm decoder state')
                values={k:sample[k] for k in KEYS} if event['flags']&4 else dict(ZERO)
                sides[side].append(dict(at_us=at,**values))
    for timeline in sides:
        for prior,current in zip(timeline,timeline[1:]):
            if current['at_us']<prior['at_us']:raise ValueError('Ambiguous post-arm group timing; reconstruction refused')
            if current['at_us']==prior['at_us'] and any(current[k]!=prior[k] for k in KEYS):raise ValueError('Conflicting simultaneous parameters')
        if not timeline or any(timeline[-1][k] for k in ('low_amplitude','high_amplitude')):raise ValueError('Final neutral source parameters required; no invented tail')
    return sides,prefix_conflicts

def reconstruct(timelines,start_us,end_us,gain=96.,maximum_offset=12):
    if not math.isfinite(gain) or gain<=0:raise ValueError('Positive fixed gain required')
    if maximum_offset!=12:raise ValueError('Candidate retains the existing +/-12 code bound')
    if not math.isfinite(start_us) or not math.isfinite(end_us) or not 0<end_us-start_us<=123000000:raise ValueError('Bounded trace window required')
    for timeline in timelines:
        for previous,current in zip(timeline,timeline[1:]):
            if current['at_us']<previous['at_us']:raise ValueError('Timeline reversal')
        for point in timeline:
            if not math.isfinite(point['at_us']):raise ValueError('Non-finite parameter time')
            if not all(math.isfinite(point[k]) for k in KEYS):raise ValueError('Non-finite source parameter')
            for band in ('low','high'):
                amp,hz=point[band+'_amplitude'],point[band+'_hz']
                if not 0<=amp<=1 or hz<=0:raise ValueError('Invalid amplitude or frequency')
                if amp and hz>=500:raise ValueError('Active frequency outside 1kHz reconstruction band')
            if gain*(point['low_amplitude']+point['high_amplitude'])>maximum_offset:raise ValueError('Gain exceeds conservative peak bound; no clipping or auto-normalization')
    pcm=[[],[]];reference=[[],[]];active=[[],[]];metrics=[]
    count=math.ceil((end_us-start_us)/1000)
    for side,timeline in enumerate(timelines):
        values=dict(ZERO);phase=[0.,0.];index=0;max_delay=0;run=longest=0;error_sq=0;max_error=0
        for n in range(count):
            at=start_us+n*1000
            while index<len(timeline) and timeline[index]['at_us']<=at:
                values=timeline[index];max_delay=max(max_delay,at-values['at_us']);index+=1
            source_active=bool(values['low_amplitude'] or values['high_amplitude'])
            x=gain*(values['low_amplitude']*math.sin(phase[0])+values['high_amplitude']*math.sin(phase[1]))
            code=round(x)
            if abs(code)>maximum_offset:raise ValueError('Unexpected sample bound breach')
            pcm[side].append(128+code);reference[side].append(x);active[side].append(source_active)
            if source_active:
                error_sq+=(code-x)**2;max_error=max(max_error,abs(code-x));run+=1;longest=max(longest,run)
            else:run=0
            for b,band in enumerate(('low','high')):phase[b]=(phase[b]+2*math.pi*values[band+'_hz']/1000)%(2*math.pi)
        if index<len(timeline):raise ValueError('Render window truncates parameter groups')
        total=sum(active[side]);energy=sum(x*x for x,a in zip(reference[side],active[side]) if a)
        metrics.append(dict(active_ms=total,longest_active_ms=longest,peak_code=max((abs(v-128) for v in pcm[side]),default=0),
            nonneutral_samples=sum(v!=128 for v in pcm[side]),quantization_error_rms=math.sqrt(error_sq/total) if total else 0,
            quantization_error_max=max_error,snr_db=10*math.log10(energy/error_sq) if energy and error_sq else None,
            zero_code_active_samples=sum(a and p==128 for a,p in zip(active[side],pcm[side])),
            maximum_parameter_grid_delay_us=max_delay,clipped_samples=0))
    return dict(pcm=pcm,reference=reference,active=active,sides=metrics,samples=count,fixed_gain=gain,sample_rate_hz=1000)
