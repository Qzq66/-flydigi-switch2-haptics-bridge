"""Replay retained real-console capture corpus; no transport or actuators."""
import json
import pathlib
from switch_hd_decode import Decoder, decode_capture

OUTPUTS=pathlib.Path(__file__).resolve().parent.parent/'outputs'
checks=[]
def check(name,condition):
    assert condition,name
    checks.append(dict(name=name,passed=True))

def decode_words(words):
    left,right=Decoder(),Decoder()
    return [(left.decode(bytes.fromhex(w)[:4]),right.decode(bytes.fromhex(w)[4:])) for w in words]

expected={'140320':163,'140937':291,'154058':18,'154812':305,'155322':305,'161720':305,'163044':305}
for stamp,count in expected.items():
    path=OUTPUTS/f'pico-continuous-capture-20261022-{stamp}.json'
    log=json.loads(path.read_text())['newest'];events=log['events']
    prefix=stamp+': '
    check(prefix+'declared and retained counts match',len(events)==count==log['total_events']==log['stored_events'])
    check(prefix+'no reported overflow or drops',log['complete'] and not log['overflow'] and log['dropped_events']==0)
    check(prefix+'event sequence contiguous',[e['sequence'] for e in events]==list(range(count)))
    check(prefix+'timestamps monotonic',all(a['at_us']<=b['at_us'] for a,b in zip(events,events[1:])))
    check(prefix+'events within capture deadline',all(0<=e['at_us']<=log['elapsed_ms']*1000 for e in events))
    words=[e['motors_hex'] for e in events if e['motors_hex'] is not None]
    check(prefix+'motor fields exactly eight bytes',all(len(bytes.fromhex(w))==8 for w in words))
    decoded=decode_capture(path)
    check(prefix+'decoder retains every motor field',len(decoded['events'])==len(words))
    check(prefix+'independent word replay agrees',[(e['left'],e['right']) for e in decoded['events']]==decode_words(words))
    samples=[s for e in decoded['events'] for side in ('left','right') for s in e[side]['samples']]
    check(prefix+'decoded state remains known',all(s['state_complete'] for s in samples))
    check(prefix+'decoded amplitudes bounded',all(0<=s[k]<=1 for s in samples for k in ('low_amplitude','high_amplitude')))
    check(prefix+'legacy log has no end confirmation evidence',log.get('stream_end') is None)

for child_stamp,log_stamp,received in [('155010','155322',303),('161338','161720',302),('162748','163044',302)]:
    child=json.loads((OUTPUTS/f'flydigi-live-bench-child-20261022-{child_stamp}.json').read_text())
    events=child['events']
    local=json.loads((OUTPUTS/f'pico-continuous-capture-20261022-{log_stamp}.json').read_text())['newest']['events']
    words=[e['motors_hex'] for e in local if e['motors_hex'] is not None]
    wire=[e['motors'] for e in events];prefix=child_stamp+': '
    check(prefix+'wire event count',len(events)==received)
    check(prefix+'wire sequences contiguous',[e['sequence'] for e in events]==list(range(received)))
    check(prefix+'wire timestamps monotonic',all(a['at_us']<=b['at_us'] for a,b in zip(events,events[1:])))
    check(prefix+'wire matches local motor prefix byte for byte',wire==words[:received])
    check(prefix+'wire and local decoding match',decode_words(wire)==decode_words(words)[:received])
    missing=words[received:]
    check(prefix+'tail completeness is explicit',missing==([] if received==303 else ['0000000000014040']))
    check(prefix+'historical child does not prove terminal handshake',not child.get('terminal_ack_replied',False))

proof=json.loads((OUTPUTS/'pico-bridge-v042-raw-test-20261022-165112.json').read_text())
check('v042 historical summary records 307 and end ack',proof['events']==307 and proof['terminal_ack_replied'] and not proof['collector_errors'])
check('v042 is summary evidence, not retained raw event replay',not isinstance(proof['events'],list))
print(json.dumps(checks))
