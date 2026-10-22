import hashlib
import json
import pathlib
import struct
import sys

profile,path=sys.argv[1],pathlib.Path(sys.argv[2])
if profile not in ('ram','flash'):raise ValueError('profile')
blob=path.read_bytes()
if profile=='flash':
    if path.suffix!='.bin' or not 0<len(blob)<=0xf0000:raise ValueError('Flash BIN bounds')
    result=dict(profile=profile,file=str(path),bytes=len(blob),minimum_address='0x10000000',
                maximum_end=hex(0x10000000+len(blob)),sha256=hashlib.sha256(blob).hexdigest(),
                program_erase_start='0x0',program_erase_end=hex((len(blob)+4095)//4096*4096),
                log_offsets=['0xf0000','0xf1000'],filesystem_start='0x100000',
                program_excludes_logs_and_filesystem=True)
    path.with_suffix('.manifest.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2));sys.exit(0)
if len(blob)%512:raise ValueError('UF2 length')
blocks=[];numbers=set();total_expected=len(blob)//512
for at in range(0,len(blob),512):
    b=blob[at:at+512]
    m0,m1,flags,address,size,number,total,family=struct.unpack_from('<8I',b)
    if (m0,m1)!=(0x0a324655,0x9e5d5157) or struct.unpack_from('<I',b,508)[0]!=0x0ab16f30:raise ValueError('UF2 magic')
    if flags&1 or size!=256 or address%256 or number in numbers or total!=total_expected:raise ValueError('UF2 structure')
    if family!=0xe48bff59:raise ValueError('Expected RP2350 ARM secure UF2 family')
    lower,upper=(0x20000000,0x20082000) if profile=='ram' else (0x10000000,0x100f0000)
    if not lower<=address or address+size>upper:raise ValueError('UF2 outside approved range')
    numbers.add(number);blocks.append((address,size))
if numbers!=set(range(total_expected)):raise ValueError('Missing UF2 blocks')
addresses=[a for a,_ in blocks]
if len(addresses)!=len(set(addresses)):raise ValueError('Overlapping UF2 blocks')
minimum=min(addresses);maximum=max(a+n for a,n in blocks)
result=dict(profile=profile,file=str(path),bytes=len(blob),blocks=len(blocks),
            minimum_address=hex(minimum),maximum_end=hex(maximum),
            sha256=hashlib.sha256(blob).hexdigest(),
            program_erase_start=hex((minimum-0x10000000)//4096*4096) if profile=='flash' else None,
            program_erase_end=hex(((maximum-0x10000000+4095)//4096)*4096) if profile=='flash' else None,
            log_offsets=['0xf0000','0xf1000'],filesystem_start='0x100000',
            program_excludes_logs_and_filesystem=profile=='flash')
path.with_suffix('.manifest.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
