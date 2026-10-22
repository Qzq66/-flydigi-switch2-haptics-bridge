# SPDX-License-Identifier: GPL-2.0-only
# Uses switch_hd_decode.py, adapted from MissionControl; see its license notice.
"""Pure wire validation; no transport or platform backend."""
import struct,zlib

class BridgeFault(RuntimeError):pass

def unpack(data,session,request):
    if len(data)<36 or data[:4]!=b'BHR2':raise BridgeFault('wire identity')
    magic,version,flags,size,nonce,number,boot,stamp,count,dropped=struct.unpack_from('<4sBBHQIIIHH',data)
    if version!=2 or flags&~31 or size!=len(data) or len(data)!=36+count*16 or count>8:raise BridgeFault('wire bounds')
    if flags&8 and flags&6:raise BridgeFault('terminal stream still active')
    if flags&16 and (not flags&8 or count):raise BridgeFault('invalid complete marker')
    if nonce!=session or number!=request:raise BridgeFault('wire session or request')
    if zlib.crc32(data[:-4])!=struct.unpack_from('<I',data,len(data)-4)[0]:raise BridgeFault('wire CRC')
    if dropped:raise BridgeFault('source queue overflow')
    events=[]
    for i in range(count):
        at,seq,motors=struct.unpack_from('<II8s',data,32+i*16)
        if (stamp-at)&0xffffffff>=0x80000000:raise BridgeFault('future source timestamp')
        events.append(dict(at_us=at,sequence=seq,motors=motors))
    return dict(flags=flags,boot=boot,source_us=stamp,events=events)

