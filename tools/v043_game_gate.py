"""Recheck the input acceptance and bind staged output to its verified firmware."""
import hashlib,json,pathlib
from assess_v043_host import assess,ROOT

def validate(program,capture,baseline,assessment,preflight):
    result=assess(program,capture,baseline,assessment.get('duration_checks',{}).get('human_inputs') is True)
    if assessment.get('status')!='PASSED_V043_SWITCH_120S_INPUT_ACCEPTANCE' or result['status']!=assessment['status'] or result['pending_checks']:
        raise ValueError('Complete recomputed v043 input acceptance is required')
    firmware=program.get('firmware_preflight',{}).get('firmware_sha256')
    if not isinstance(firmware,str) or len(firmware)!=64 or preflight.get('verified') is not True or preflight.get('variant')!='v043' or preflight.get('firmware_sha256')!=firmware:
        raise ValueError('Actual board must run the same accepted v043 image')
    generation=preflight.get('baseline_generation');accepted=capture['generation']
    if type(generation) is not int or not 0<=((generation-accepted)&0xffffffff)<0x80000000:raise ValueError('Current journal baseline predates accepted input evidence')
    return dict(verified=True,firmware_sha256=firmware,accepted_input_generation=accepted,
        staged_click_required=True,prompt_ms=120,maximum_offset=12,maximum_prompts_per_side=3,wire_timeout_ms=80)

def authorize(bundle_path,preflight):
    bundle=json.loads(pathlib.Path(bundle_path).read_text(encoding='utf-8'));data={}
    for key in ('program','capture','baseline','assessment'):
        item=bundle['sources'][key];relative=pathlib.PurePosixPath(item['path'])
        if len(relative.parts)!=2 or relative.parts[0]!='docs' or relative.suffix!='.json' or '..' in relative.parts:raise ValueError('Only flat public docs evidence paths are allowed')
        raw=(ROOT/relative).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=item['sha256']:raise ValueError('Prerequisite evidence changed: '+key)
        data[key]=json.loads(raw.decode('utf-8-sig'))
    result=validate(data['program'],data['capture']['newest'],data['baseline']['newest'],data['assessment'],preflight)
    result['source_hashes']={k:v['sha256'] for k,v in bundle['sources'].items()}
    return result
