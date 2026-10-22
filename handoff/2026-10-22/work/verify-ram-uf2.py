import json
import pathlib
import struct
import sys

path = pathlib.Path(sys.argv[1])
data = path.read_bytes()
assert len(data) % 512 == 0, 'Invalid UF2 length'
addresses = []
for offset in range(0, len(data), 512):
    block = data[offset:offset+512]
    magic0, magic1, flags, address, size, number, total, family = struct.unpack_from('<8I', block)
    assert (magic0, magic1) == (0x0A324655, 0x9E5D5157)
    assert struct.unpack_from('<I', block, 508)[0] == 0x0AB16F30
    assert not (flags & 1), 'Non-main-flash block needs separate analysis'
    assert size <= 476
    assert 0x20000000 <= address and address + size <= 0x20082000, 'Non-SRAM target detected'
    addresses.append((address, size))
print(json.dumps(dict(blocks=len(addresses), minimum_address=hex(min(a for a, _ in addresses)), maximum_end=hex(max(a+s for a,s in addresses)), all_blocks_in_sram=True), indent=2))
