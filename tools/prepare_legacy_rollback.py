"""Freeze the retained Windows notification baseline without touching hardware."""
import argparse,datetime,hashlib,json,pathlib,shutil
ROOT=pathlib.Path(__file__).absolute().parents[1]
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--original-root',type=pathlib.Path,required=True);args=parser.parse_args()
    old=args.original_root;stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    image=old/'outputs/pico-haptics-bridge-v040/flash/pico_pro_capture.bin';backup=old/'work/backups/pico-pre-capture-20261022-124037.bin'
    assert image.stat().st_size==354708 and digest(image)=='0cef76fe7ade60477d5f375a83830ac5877c39b9e28ed677a9cd595049904f34'
    assert backup.stat().st_size==4194304 and digest(backup)=='09762691d3fddf3ba592db0bb6f520cb2384423f37194e7974089c9b0f700593'
    proof=json.loads((old/'outputs/bridge-v041-final-live-proof.json').read_text(encoding='utf-8'))
    assert proof['passed_limited_perceptible_prompt_test'] and all(proof['checks'].values())
    private=ROOT/'handoff/2026-10-22/work/private';dest=private/('rollback-v041-'+stamp)
    work=dest/'work';out=dest/'outputs';work.mkdir(parents=True);out.mkdir();(work/'private').mkdir()
    files=['bridge_runtime.py','bridge-switch-live.py','bridge_input.py','xinput_readonly.py','switch_hd_decode.py','flydigi-live-bridge-bench.py','flydigi-owner-hotplug.py','flydigi-safe-waveform.py','flydigi-readonly.py','test-pico-bridge-v040.py','test-pico-capture-v035-ram.py','pico-hotspot.ps1','restore-pico-hotspot.ps1']
    hashes={}
    for name in files:
        src=old/'work'/name;shutil.copy2(src,work/name);hashes[name]=digest(src)
    for name in ('bridge-network.xml','bridge-session.json'):
        shutil.copy2(old/'work/private'/name,work/'private'/name)
    for name in ('flydigi-runtime-exit-validation.json','bridge-v041-final-live-proof.json','bridge-v041-final-human-feedback.json'):
        shutil.copy2(old/'outputs'/name,out/name)
    shutil.copy2(image,dest/'legacy-v040.bin');shutil.copy2(backup,dest/'original-flash.bin')
    selection=dict(root=str(dest),original_root=str(old),firmware=str(dest/'legacy-v040.bin'),original_flash=str(dest/'original-flash.bin'),entry=str(work/'bridge-switch-live.py'),prompt_ms=120,prompt_offset=12,game_pilot=False)
    (private/'rollback-selection.json').write_text(json.dumps(selection,indent=2),encoding='utf-8')
    report=dict(status='PREPARED_NOT_INSTALLED',target='retained pre-Mac Windows v040 firmware and v041 perceptible notification mode',pico_flash_writes=0,flydigi_writes=0,firmware_sha256=digest(image),original_flash_sha256=digest(backup),source_hashes=hashes,prompt_ms=120,prompt_offset=12,known_limitations=['302 of 303 fields in final old trial; missing neutral tail','no full game validation','no guarantee of eliminating current wireless timing gaps'],private_snapshot='ignored work/private/rollback-v041-'+stamp)
    output=ROOT/'docs'/('WINDOWS_ROLLBACK_PREPARATION_'+stamp+'.json');output.write_text(json.dumps(report,indent=2),encoding='utf-8');print(str(output))
if __name__=='__main__':main()
