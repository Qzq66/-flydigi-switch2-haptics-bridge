"""Compare real host journal with received stream and strict input/end evidence."""
import argparse,json,pathlib,sys
ROOT=pathlib.Path(__file__).absolute().parents[1];sys.path.insert(0,str(ROOT/'handoff/2026-10-22/work'))
from bridge_process import input_end_check_succeeded
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--program',type=pathlib.Path,required=True);p.add_argument('--capture',type=pathlib.Path,required=True);p.add_argument('--baseline',type=pathlib.Path);p.add_argument('--output',type=pathlib.Path,required=True);a=p.parse_args()
program=json.loads(a.program.read_text(encoding='utf-8-sig'));child=program.get('child',{})
capture=json.loads(a.capture.read_text(encoding='utf-8-sig'))['newest']
local=[e['motors_hex'] for e in capture['events'] if e['motors_hex'] is not None]
wire=child.get('events',[]);changes=child.get('input_relay',{}).get('changes',[])
states=[e['pro_input'] for e in changes]
checks=dict(strict_child_passed=input_end_check_succeeded(child,program.get('child_exit')),
    parent_program_passed=program.get('status')=='PASSED_V042_SWITCH_INPUT_END_PROGRAM_CHECKS',
    local_crc_valid=capture['crc_valid'],local_complete=capture['complete'],
    persistent_END2_confirmed=capture['stream_end']=='client_confirmed',
    all_motor_fields_exact=local==[e['motors'] for e in wire],
    wire_sequence_contiguous=[e['sequence'] for e in wire]==list(range(len(wire))),
    bottom_button_sampled='040000000880000880' in states,
    right_button_sampled='080000000880000880' in states,
    last_input_neutral=bool(states) and states[-1]=='000000000880000880',
    no_child_motor_output=child.get('motor_output_enabled') is False and child.get('output_frames')==0,
    parent_disabled=program.get('runtime_disable_ack') is True,configuration_unchanged=program.get('configuration_unchanged') is True)
if a.baseline:
    baseline=json.loads(a.baseline.read_text(encoding='utf-8-sig'))['newest']
    delta=(capture['generation']-baseline['generation'])&0xffffffff
    checks['new_log_generation']=0<delta<0x80000000
result=dict(status='PASSED_V042_INPUT_END_DATA_CHECKS' if all(checks.values()) else 'INCOMPLETE',checks=checks,
    local_motor_fields=len(local),received_motor_fields=len(wire),log_generation=capture['generation'],
    source_reports=[a.program.name,a.capture.name],human_screen_confirmation='record separately; PC sampled inputs alone do not prove host display',game_test=False)
with a.output.open('x',encoding='utf-8') as h:json.dump(result,h,indent=2)
print(json.dumps(result,indent=2));raise SystemExit(0 if all(checks.values()) else 1)
