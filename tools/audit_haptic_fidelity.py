"""Inspect accepted real traces as data; never sends haptics or changes settings."""
import argparse,collections,hashlib,json,pathlib,sys
ROOT=pathlib.Path(__file__).absolute().parents[1];WORK=ROOT/'handoff/2026-10-22/work'
sys.path.insert(0,str(WORK))
from switch_hd_decode import Decoder

def analyze(events,arm_source):
    sides=[]
    for side in (0,1):
        decoder=Decoder();frequencies=collections.Counter();formats=collections.Counter()
        active=[];unknown=0;overlaps=0;last_group=None;above=0
        for event in events:
            result=decoder.decode(bytes.fromhex(event['motors'])[4*side:4*side+4]);formats[result['format']]+=1
            for i,sample in enumerate(result['samples']):
                at=event['at_us']+i*5000
                if last_group is not None and at<last_group:overlaps+=1
                last_group=at
                if at<arm_source or not event.get('flags',0)&4:continue
                if not sample['state_complete']:unknown+=1;continue
                if not(sample['low_amplitude'] or sample['high_amplitude']):continue
                active.append(sample)
                for band in ('low','high'):
                    if sample[band+'_amplitude']:
                        hz=sample[band+'_hz'];frequencies[round(hz,6)]+=1;above+=hz>=500
        amplitudes=[s[band+'_amplitude'] for s in active for band in ('low','high') if s[band+'_amplitude']]
        sums=[s['low_amplitude']+s['high_amplitude'] for s in active]
        sides.append(dict(active_parameter_groups=len(active),active_frequency_histogram_hz=[dict(hz=hz,groups=n) for hz,n in sorted(frequencies.items())],
            active_normalized_amplitude_range=[min(amplitudes),max(amplitudes)] if amplitudes else None,
            maximum_sum_of_band_amplitudes=max(sums,default=0),
            legacy_gain5_peak_code_bound=max(sums,default=0)*5,
            legacy_gain5_groups_guaranteed_round_to_zero=sum(5*a<.5 for a in sums),
            active_band_groups_at_or_above_500_hz=above,unknown_postarm_groups=unknown,
            assumed_5ms_group_order_overlaps=overlaps,word_formats=dict(formats)))
    return sides

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=pathlib.Path,required=True);args=parser.parse_args()
    if args.output.exists():parser.error('Preserve prior evidence; choose a new output')
    def guard(event,values):
        if event.startswith('socket.') or event in ('ctypes.dlopen','subprocess.Popen','os.system'):raise RuntimeError('Offline audit denied I/O: '+event)
    sys.addaudithook(guard)
    sources={};trials=[]
    for stamp in ('20261024-131624','20261024-132744','20261024-135514','20261024-140244'):
        path=ROOT/'docs'/('WINDOWS_V043_GAME_RECHECK_'+stamp+'.json');program=json.loads(path.read_text(encoding='utf-8-sig'))
        if program['status']!='PASSED_V043_SWITCH_GAME_PROGRAM_CHECKS' or not program['configuration_unchanged']:raise ValueError('Accepted program evidence required')
        child=program['child'];anchor=child['source_clock_anchor'];arm=anchor['source_us']+(child['armed_at_pc_clock']-anchor['pc_clock'])*1e6
        trials.append(dict(stamp=stamp,scene=program['scene'],motor_fields=len(child['events']),sides=analyze(child['events'],arm)))
        sources[path.relative_to(ROOT).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
    for path in (pathlib.Path(__file__),WORK/'switch_hd_decode.py',WORK/'bridge_render.py'):
        sources[path.relative_to(ROOT).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
    report=dict(status='OFFLINE_FIDELITY_PROTOCOL_AUDIT_COMPLETE',device_access=False,network_access=False,io_guard=True,
        waveform_rendered=False,physical_fidelity_validated=False,trials=trials,source_sha256=sources,
        assumptions=['Decoded amplitudes are protocol values, not measured force or displacement.','5ms per parameter group remains the current experimental scheduling assumption.','1kHz is the existing output implementation; no higher device rate is established.','Zero quantization bound describes gain5 original path, not the successful fixed notification mode.'])
    with args.output.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
    print(json.dumps(dict(status=report['status'],trials=[dict(stamp=t['stamp'],sides=[dict(active_groups=s['active_parameter_groups'],hz=[x['hz'] for x in s['active_frequency_histogram_hz']],gain5_zero_groups=s['legacy_gain5_groups_guaranteed_round_to_zero'],gain5_peak_code_bound=s['legacy_gain5_peak_code_bound'],high_frequency_groups=s['active_band_groups_at_or_above_500_hz'],timing_overlaps=s['assumed_5ms_group_order_overlaps']) for s in t['sides']]) for t in trials]),indent=2))

if __name__=='__main__':main()
