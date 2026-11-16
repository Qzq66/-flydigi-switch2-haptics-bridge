"""Decode source activity episodes; pure data, no actuator or timing claims."""
from switch_hd_decode import Decoder

def source_episodes(wire,arm_source):
    decoders=[Decoder(),Decoder()];previous=[False,False];neutral_at=[None,None]
    starts=[[],[]];quiet=[[],[]];complete=True
    for event in wire:
        raw=bytes.fromhex(event['motors'])
        for side,word in enumerate((raw[:4],raw[4:])):
            for i,sample in enumerate(decoders[side].decode(word)['samples']):
                at=event['at_us']+i*5000
                complete=complete and sample['state_complete']
                active=bool(event.get('flags',0)&4 and sample['state_complete'] and (sample['low_amplitude'] or sample['high_amplitude']))
                if not active and previous[side]:neutral_at[side]=at
                if active and not previous[side] and arm_source is not None and at>=arm_source:
                    if starts[side]:quiet[side].append(None if neutral_at[side] is None else at-neutral_at[side])
                    starts[side].append(at)
                previous[side]=active
    return dict(starts_us=starts,quiet_gaps_us=quiet,state_complete=bool(complete))
