"""Offline readback checks: exact motor words and all Flash write bounds."""
import pathlib,json,hashlib
root=pathlib.Path(__file__).absolute().parent.parent
log=json.loads((root/'outputs/pico-continuous-capture-20261022-140320.json').read_text(encoding='utf-8-sig'))['newest']
exercise=json.loads((root/'outputs/pico-v035-flash-exercise.json').read_text(encoding='utf-8'))
manifest=json.loads((root/'outputs/pico-pre-capture-backup.json').read_text(encoding='utf-8-sig'))
original=pathlib.Path(manifest['path']).read_bytes()
actual=(root/'work/backups/pico-v035-after-pc-flash.bin').read_bytes()
checks=[]
def check(name,ok):checks.append(dict(name=name,passed=bool(ok)));assert ok,name
check('complete_Flash_capture_CRC',log['crc_valid'] and log['complete'] and not log['no_flash_marker'])
check('all_160_motor_words_exact',[e['motors_hex'] for e in log['events'] if e['report_id']=='10']==exercise['expected_words'])
check('whole_readback_4MiB',len(actual)==len(original)==4194304)
check('original_backup_hash',hashlib.sha256(original).hexdigest().upper()==manifest['sha256'])
check('only_program_and_selected_log_slot_changed',actual[0x6000:0xe0000]==original[0x6000:0xe0000] and actual[0xf0000:]==original[0xf0000:])
check('filesystem_unchanged',actual[0x100000:]==original[0x100000:])
check('expected_log_slot',log['target_offset']=='0xe0000' and actual[0xe0000:0xe0008]==b'BPROLOG5')
out=root/'outputs/pico-v035-flash-verification.json'
out.write_text(json.dumps(dict(checks=checks,status='PASSED'),indent=2),encoding='utf-8')
print(json.dumps(checks,indent=2))
