"""Export numeric candidate previews; no WAV, device writes or live bridge hook."""
import argparse,csv,hashlib,json,pathlib,sys,unittest
from haptic_fidelity_candidate import decode_timeline,reconstruct
ROOT=pathlib.Path(__file__).absolute().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output-dir',type=pathlib.Path,required=True);a=parser.parse_args()
    if a.output_dir.exists():parser.error('Use a new output folder; preserve existing evidence')
    def guard(event,args):
        if event.startswith('socket.') or event in ('ctypes.dlopen','subprocess.Popen','os.system'):raise RuntimeError('Offline reconstruction blocked I/O: '+event)
    sys.addaudithook(guard)
    tests=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.discover(str(ROOT/'tools'),pattern='test_haptic_fidelity*.py'))
    if not tests.wasSuccessful():raise ValueError('Offline fidelity tests failed; no candidate exported')
    a.output_dir.mkdir(parents=True)
    trials=[];hashes={}
    for stamp in ('20261024-131624','20261024-132744','20261024-135514','20261024-140244'):
        path=ROOT/'docs'/('WINDOWS_V043_GAME_RECHECK_'+stamp+'.json');p=json.loads(path.read_text(encoding='utf-8-sig'))
        if p['status']!='PASSED_V043_SWITCH_GAME_PROGRAM_CHECKS' or not p['configuration_unchanged']:raise ValueError('Accepted trace required')
        c=p['child'];anchor=c['source_clock_anchor'];arm=anchor['source_us']+(c['armed_at_pc_clock']-anchor['pc_clock'])*1e6
        timelines,conflicts=decode_timeline(c['events'],arm)
        end=max(c['events'][-1]['at_us'],max(t[-1]['at_us'] for t in timelines))+2000
        result=reconstruct(timelines,arm,end,gain=96)
        # Preview retains all active source samples and 5ms edge margins.
        # Silent gaps are omitted explicitly; sample indices never renumbered.
        selected=set()
        for side in result['active']:
            for n,active in enumerate(side):
                if active:selected.update(range(max(0,n-5),min(result['samples'],n+6)))
        preview=a.output_dir/(stamp+'-active-windows.csv')
        with preview.open('x',encoding='utf-8',newline='') as f:
            writer=csv.writer(f);writer.writerow(('sample_index','ms_after_arm','left_pcm','right_pcm','left_reference_offset','right_reference_offset'))
            for n in sorted(selected):writer.writerow((n,n,*[side[n] for side in result['pcm']],*[round(side[n],8) for side in result['reference']]))
        parameters=a.output_dir/(stamp+'-parameters.json')
        parameters.write_text(json.dumps(dict(arm_source_us=arm,group_interval_us_assumed=5000,timelines=timelines),indent=2),encoding='utf-8')
        trials.append(dict(stamp=stamp,scene=p['scene'],sample_count=result['samples'],fixed_gain=96,sample_rate_hz=1000,sides=result['sides'],
            excluded_prearm_group_order_conflicts=conflicts,postarm_group_order_conflicts=0,
            parameter_file=parameters.name,parameter_sha256=hashlib.sha256(parameters.read_bytes()).hexdigest(),
            preview_file=preview.name,preview_rows=len(selected),preview_sha256=hashlib.sha256(preview.read_bytes()).hexdigest()))
        hashes[path.relative_to(ROOT).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
    for path in (pathlib.Path(__file__),ROOT/'tools/haptic_fidelity_candidate.py',ROOT/'tools/audit_haptic_fidelity.py',ROOT/'tools/test_haptic_fidelity_candidate.py',ROOT/'tools/test_haptic_fidelity_audit.py',ROOT/'handoff/2026-10-22/work/switch_hd_decode.py'):
        hashes[path.relative_to(ROOT).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
    report=dict(status='OFFLINE_CANDIDATE_RECONSTRUCTED',device_access=False,network_access=False,io_guard=True,live_output_enabled=False,
        physical_fidelity_validated=False,tests_run=tests.testsRun,tests_passed=True,frequency_mapping='Two independent oscillators per grip at decoded frequencies',amplitude_mapping='Global fixed gain96, no per-event normalization, no clipping',
        limitations=['5ms parameter-group scheduling remains an assumption.','Initial oscillator phase is an explicit zero-phase convention, not recovered actuator phase.','1000Hz PCM and +/-12 code bound; active frequencies >=500Hz refused.','Source timing is USB reception, not original effect-generation time.','CSV omits long silent gaps; original sample indices retain timing.','Gain96 is an offline numerical candidate, not physical calibration or a hardware playback authorization.'],
        trials=trials,source_sha256=hashes)
    with (a.output_dir/'REPORT.json').open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
    print(json.dumps({k:v for k,v in report.items() if k not in ('source_sha256','limitations')},indent=2))

if __name__=='__main__':main()
