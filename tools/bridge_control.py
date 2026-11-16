"""Stable bridge command entry; status is local-only and never opens devices."""
import argparse,json,pathlib,subprocess,sys
ROOT=pathlib.Path(__file__).absolute().parents[1];PRIVATE=ROOT/'handoff/2026-10-22/work/private'
def status(mode="single"):
    selection=json.loads((PRIVATE/'v043-install-selection.json').read_text());record=json.loads(pathlib.Path(selection['record']).read_text())
    plan_path=ROOT/('docs/MULTI_GAME_G58_PLAN_2026-10-30.json' if mode=='multi' else 'docs/UPDATED_GAME_G57_PLAN_2026-10-29.json');plan=json.loads(plan_path.read_text())
    ready=record['baseline_generation']==plan['expected_flash_generation'] and record['installed_snapshot_sha256']==plan['expected_full_flash_sha256']
    return dict(mode=mode,recorded_board_generation=record['baseline_generation'],plan_generation=plan['expected_flash_generation'],plan_binding_matches_record=ready,
        hardware_checked_now=False,automatic_output=False,multi_event='independent_candidate_not_hardware_validated',next_action='run existing hardware preflight' if ready else 'rebind accepted plan to current verified board snapshot before run')
def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=('status','run'),nargs='?',default='status');p.add_argument('--mode',choices=('single','multi'),default='single');a=p.parse_args();s=status(a.mode);print(json.dumps(s,indent=2))
    if a.action=='status':return 0
    if not s['plan_binding_matches_record']:print('RUN_BLOCKED: stale plan binding; no device command sent');return 2
    pic=ROOT.parent/'pico-work-20261022/picotool-2.3.1/picotool/picotool.exe'
    return subprocess.call([sys.executable,'-B',str(ROOT/('tools/run_multi_game_g58.py' if a.mode=='multi' else 'tools/run_updated_game_g57.py')),'--play',str(ROOT/('docs/MULTI_GAME_G58_PLAN_2026-10-30.json' if a.mode=='multi' else 'docs/UPDATED_GAME_G57_PLAN_2026-10-29.json')),'--picotool',str(pic)])
if __name__=='__main__':raise SystemExit(main())
