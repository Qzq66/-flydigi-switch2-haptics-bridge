"""Package already completed input evidence; does not access devices."""
import argparse,hashlib,json,pathlib
from v043_game_gate import ROOT,validate
p=argparse.ArgumentParser(description=__doc__)
for name in ('program','capture','baseline','assessment','output'):p.add_argument('--'+name,type=pathlib.Path,required=True)
a=p.parse_args();data={};sources={}
for key in ('program','capture','baseline','assessment'):
    path=getattr(a,key);raw=path.read_bytes();data[key]=json.loads(raw.decode('utf-8-sig'));sources[key]=dict(path=path.absolute().relative_to(ROOT).as_posix(),sha256=hashlib.sha256(raw).hexdigest())
preflight=dict(data['program']['firmware_preflight'],baseline_generation=data['capture']['newest']['generation'])
result=validate(data['program'],data['capture']['newest'],data['baseline']['newest'],data['assessment'],preflight)
with a.output.open('x',encoding='utf-8') as h:json.dump(dict(status='V043_STAGED_GAME_PREREQUISITE_VERIFIED',sources=sources,authorization=result),h,indent=2)
print(json.dumps(result,indent=2))
