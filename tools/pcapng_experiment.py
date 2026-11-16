"""Bounded PCAPNG/IPv4 UDP parser, retaining section/interface and timestamp units."""
import struct
from fractions import Fraction

def options(data,endian):
    out={};pos=0
    while pos<len(data):
        if len(data)-pos<4:raise ValueError('Truncated option')
        code,size=struct.unpack_from(endian+'HH',data,pos);pos+=4
        if code==0:
            if size:raise ValueError('Invalid option end')
            break
        if pos+size>len(data):raise ValueError('Option bounds')
        out.setdefault(code,[]).append(data[pos:pos+size]);pos+=(size+3)&~3
    return out

def packets(data):
    if len(data)>128*1024*1024:raise ValueError('Capture size bound')
    pos=0;endian=None;interfaces=[];section=-1
    while pos<len(data):
        if len(data)-pos<12:raise ValueError('Truncated block')
        if data[pos:pos+4]==b'\x0a\x0d\x0d\x0a':
            bom=data[pos+8:pos+12]
            endian={b'\x4d\x3c\x2b\x1a':'<',b'\x1a\x2b\x3c\x4d':'>'}.get(bom)
            if endian is None:raise ValueError('Section byte order')
            interfaces=[];section+=1
        if endian is None:raise ValueError('Missing section')
        kind,size=struct.unpack_from(endian+'II',data,pos)
        if size<12 or size%4 or size>16*1024*1024 or pos+size>len(data):raise ValueError('Block bounds')
        if struct.unpack_from(endian+'I',data,pos+size-4)[0]!=size:raise ValueError('Block length mismatch')
        body=data[pos+8:pos+size-4];pos+=size
        if kind==0x0a0d0d0a:
            if len(body)<16:raise ValueError('Section header bounds')
        elif kind==1:
            if len(body)<8:raise ValueError('Interface bounds')
            link,reserved,snap=struct.unpack_from(endian+'HHI',body);opts=options(body[8:],endian)
            resol=opts.get(9,[b'\x06'])[0]
            if len(resol)!=1:raise ValueError('Timestamp resolution')
            denominator=2**(resol[0]&127) if resol[0]&128 else 10**resol[0]
            offset=opts.get(14,[b'\0'*8])[0]
            if len(offset)!=8:raise ValueError('Timestamp offset')
            interfaces.append((link,Fraction(1_000_000_000,denominator),struct.unpack(endian+'q',offset)[0]*1_000_000_000))
        elif kind==6:
            if len(body)<20:raise ValueError('Packet header bounds')
            interface,hi,lo,cap,original=struct.unpack_from(endian+'IIIII',body)
            if interface>=len(interfaces) or cap>original or 20+((cap+3)&~3)>len(body):raise ValueError('Packet bounds')
            link,unit,offset=interfaces[interface];opts=options(body[20+((cap+3)&~3):],endian)
            drop=opts.get(4,[b'\0'*8])[0]
            if len(drop)!=8:raise ValueError('Packet drop count')
            flags=opts.get(2,[b'\0'*4])[0]
            if len(flags)!=4:raise ValueError('Packet flags')
            yield dict(section=section,interface=interface,linktype=link,
                timestamp_ns=int(((hi<<32)|lo)*unit)+offset,timestamp_quantum_ns=float(unit),
                captured_length=cap,original_length=original,truncated=cap!=original,
                reported_drops=struct.unpack(endian+'Q',drop)[0],direction=struct.unpack(endian+'I',flags)[0]&3,data=body[20:20+cap])
        elif kind==3:raise ValueError('Simple packet block has no usable timestamp')

def udp_payload(packet):
    data=packet['data'];link=packet['linktype'];offset=0
    if link==1:
        if len(data)<14:raise ValueError('Ethernet bounds')
        ether=struct.unpack_from('!H',data,12)[0];offset=14
        for _ in range(2):
            if ether not in (0x8100,0x88a8):break
            if len(data)<offset+4:raise ValueError('VLAN bounds')
            ether=struct.unpack_from('!H',data,offset+2)[0];offset+=4
        if ether!=0x0800:return None
    elif link not in (101,228):raise ValueError('Unsupported link type')
    if len(data)<offset+20:return None
    if data[offset]>>4!=4:return None
    ihl=(data[offset]&15)*4;total=struct.unpack_from('!H',data,offset+2)[0]
    if ihl<20 or total<ihl+8 or offset+total>len(data):raise ValueError('IPv4 bounds')
    if data[offset+9]!=17:return None
    if struct.unpack_from('!H',data,offset+6)[0]&0x3fff:raise ValueError('Fragmented experiment packet')
    start=offset+ihl;source,destination,length=struct.unpack_from('!HHH',data,start)
    if 49724 not in (source,destination):return None
    if length<8 or start+length>offset+total:raise ValueError('UDP bounds')
    return data[start+8:start+length]
