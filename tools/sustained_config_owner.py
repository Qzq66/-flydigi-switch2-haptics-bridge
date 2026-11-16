"""Separate current-configuration read gate; old owner/proof remain unchanged."""
import json,pathlib,sys,hashlib
ROOT=pathlib.Path(__file__).absolute().parents[1];PRIVATE=ROOT/'handoff/2026-10-22/work/private'
sys.path.insert(0,str(ROOT/'handoff/2026-10-22/work'))
def validate_proof(proof,expected):
    if proof.get('status')!='PASSED_UPDATED_CONFIG_AMP9_120MS_EXIT_AND_NATIVE_RECOVERY' or not proof.get('checks') or not all(proof['checks'].values()):raise ValueError('Updated exit proof incomplete')
    normal=json.loads((ROOT/'handoff/2026-10-22/outputs/flydigi-runtime-exit-validation.json').read_text(encoding='utf-8'))
    stage=json.loads((ROOT/'docs/CONFIG_STAGE_ASSESSMENT_2026-11-15.json').read_text())
    if not all(stage['checks'].values()) or stage['status']!='PASSED_FIRST_OF_TWO_ISOLATED_RUNTIME_STAGE_TEST':raise ValueError('Isolated lifecycle proof required')
    if hashlib.sha256(bytes.fromhex(expected['ram']['motors']['raw_hex'])).hexdigest()!=normal['motor_ram_sha256'] or expected['identity_sha256']!=normal['identity_sha256']:raise ValueError('Normal motor baseline mismatch')
    if proof['custom_peak_code_offset']!=9 or proof['custom_source_ms']!=120:raise ValueError('Unexpected validated envelope')
def load_owner():
    from bridge_windows import load_owner as original
    owner=original();selection=json.loads((PRIVATE/'startup-config-selection-2026-11-15.json').read_text());snapshot=pathlib.Path(selection['current_configuration_backup']);old=json.loads(snapshot.read_text());assert hashlib.sha256(snapshot.read_bytes()).hexdigest()==selection['sha256'],'Current snapshot changed';normalpath=PRIVATE/'config-read-control-raw-20261115-154118.json';normalproof=json.loads((ROOT/'docs/CONFIG_READ_CONTROL_20261115-154118.json').read_text());assert hashlib.sha256(normalpath.read_bytes()).hexdigest()==normalproof['raw_evidence_sha256'],'Normal evidence changed';normal=json.loads(normalpath.read_text())['samples'][0];expected=dict(identity_sha256=old['identity_sha256'],state=normal['state_before'],ram=normal['ram']);assert all(expected['ram'][k]['raw_hex']==old['ram'][k]['raw_hex'] for k in ('global','mapping','lighting')),'Other config changed';proof=json.loads((ROOT/'docs/UPDATED_CONFIG_AMP9_ASSESSMENT_2026-10-29.json').read_text());validate_proof(proof,expected)
    def backup(reader,path):
        uid=owner.safe.digest(reader.ask(4,reply_size=16))
        if uid!=expected['identity_sha256']:raise ValueError('Updated controller identity mismatch')
        result=dict(device=dict(identity_sha256=uid),state_before=list(reader.state()),ram={},scope='Current configuration read only, independent update proof; no factory writes')
        if result['state_before']!=expected['state']:raise ValueError('Current state changed since updated backup')
        for rid,label in ((1,'global'),(4,'mapping'),(5,'lighting'),(6,'motors')):
            data,summary=owner.safe.read_ram(reader,rid)
            if data.hex()!=expected['ram'][label]['raw_hex']:raise ValueError('Updated configuration changed: '+label)
            result['ram'][label]=dict(ram_id=rid,raw_hex=data.hex(),**summary)
        owner.identity(reader,result)
        if list(reader.state())!=result['state_before']:raise ValueError('State changed during updated backup')
        with path.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
        if json.loads(path.read_text())!=result:raise ValueError('Updated backup readback mismatch')
        return result
    owner.backup=backup
    owner.updated_validated_envelope=dict(maximum_offset=9,source_ms=120)
    return owner
