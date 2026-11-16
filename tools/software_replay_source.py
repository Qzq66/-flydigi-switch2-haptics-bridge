"""Explicit synthetic source profiles for host-only replay; not captured game data."""
NEUTRAL=bytes.fromhex('0001404000014040')
ACTIVE=((1<<30)|(16<<23)|(64<<16)|(64<<2)).to_bytes(4,'little')*2
START_SECONDS=(5,15,25,35,45,55)

def schedule(armed_at, origin, pulse_ms=8):
    if pulse_ms not in (8,280):
        raise ValueError('Only declared 8/280ms software comparison profiles allowed')
    rows=[]
    for second in START_SECONDS:
        at=round((armed_at-origin+second)*1e6)
        rows.extend([(at,ACTIVE),(at+pulse_ms*1000,NEUTRAL)])
    return rows
