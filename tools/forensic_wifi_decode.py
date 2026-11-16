"""Offline plaintext 802.11/LLC evidence only, gated by existing app hashes.

Does not decrypt, accept bridge packets or change the normal capture parser.
"""
import hashlib,struct,zlib
from pcapng_experiment import udp_payload

def known_wifi_payload(data,expected_hashes):
    if len(data)<32:return None
    control=struct.unpack_from('<H',data)[0]
    if control&3 or (control>>2)&3!=2:return None
    subtype=(control>>4)&15
    if subtype not in (0,8) or control&0x0400:return None
    if struct.unpack_from('<H',data,22)[0]&15:return None
    size=24+(6 if control&0x0300==0x0300 else 0)
    if subtype==8:
        if len(data)<size+2 or data[size]&0x80:return None
        size+=2
        if control&0x8000:size+=4
    if data[size:size+8]!=b'\xaa\xaa\x03\x00\x00\x00\x08\x00':return None
    try:payload=udp_payload(dict(data=data[size+8:],linktype=101))
    except (ValueError,IndexError,struct.error):return None
    if payload is None or len(payload)<36 or payload[:4]!=b'BHR2' or payload[4]!=2:return None
    count=struct.unpack_from('<H',payload,28)[0]
    if count>8 or len(payload)!=36+count*16 or struct.unpack_from('<H',payload,6)[0]!=len(payload):return None
    if zlib.crc32(payload[:-4])!=struct.unpack_from('<I',payload,len(payload)-4)[0]:return None
    if hashlib.sha256(payload).hexdigest() not in expected_hashes:return None
    return payload
