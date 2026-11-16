"""Validated archived motor excerpt, repeated on an explicitly synthetic schedule."""
import math,pathlib,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'handoff/2026-10-22/work'))
from software_replay_source import START_SECONDS
from switch_hd_decode import Decoder

START_INDEX=465
END_INDEX=486  # exclusive; includes neutral field after activity
ACTIVE_INDEX=466

def _decode(decoders, row):
    raw=bytes.fromhex(row['motors'])
    if len(raw)!=8:raise ValueError('Invalid archived motor length')
    return [decoders[i].decode(raw[i*4:i*4+4]) for i in (0,1)]

def prepare(events):
    if len(events)<END_INDEX:raise ValueError('Archived excerpt unavailable')
    complete=[Decoder(),Decoder()];decoded=[]
    for row in events[:END_INDEX]:decoded.append(_decode(complete,row))
    rows=events[START_INDEX:END_INDEX];fresh=[Decoder(),Decoder()]
    for i,row in enumerate(rows):
        if row['flags']!=7:raise ValueError('Excerpt requires configured active upstream')
        if i and row['at_us']<=rows[i-1]['at_us']:raise ValueError('Excerpt time not strictly increasing')
        value=_decode(fresh,row)
        if value!=decoded[START_INDEX+i]:raise ValueError('Excerpt depends on omitted decoder history')
        for side in value:
            for sample in side['samples']:
                if not sample['state_complete']:raise ValueError('Incomplete decoder state')
                values=[sample[k] for k in ('low_amplitude','low_hz','high_amplitude','high_hz')]
                if not all(math.isfinite(x) for x in values):raise ValueError('Invalid decoded value')
                if 96*(values[0]+values[2])>9:raise ValueError('Existing conservative bound exceeded')
                if any(a and f>=500 for a,f in ((values[0],values[1]),(values[2],values[3]))):raise ValueError('Existing frequency bound exceeded')
    def neutral(v):return all(not(s['low_amplitude'] or s['high_amplitude']) for side in v for s in side['samples'])
    if not neutral(decoded[START_INDEX]) or not neutral(decoded[END_INDEX-1]):raise ValueError('Excerpt must begin/end neutral')
    if all(neutral(v) for v in decoded[START_INDEX:END_INDEX]):raise ValueError('Excerpt has no activity')
    # A second instance must also decode identically after the first ends.
    for i,row in enumerate(rows):
        if _decode(fresh,row)!=decoded[START_INDEX+i]:raise ValueError('Repeat changes decoder state')
    anchor=events[ACTIVE_INDEX]['at_us']
    return [(r['at_us']-anchor,bytes.fromhex(r['motors'])) for r in rows]

def schedule(excerpt,armed_at,origin):
    result=[]
    for second in START_SECONDS:
        base=round((armed_at-origin+second)*1e6)
        result.extend((base+offset,raw) for offset,raw in excerpt)
    return result
