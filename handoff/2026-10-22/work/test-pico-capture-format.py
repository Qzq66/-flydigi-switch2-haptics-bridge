import importlib.util
import pathlib
import struct
import zlib

path=pathlib.Path(__file__).with_name('pico_capture_log.py')
sp=importlib.util.spec_from_file_location('capture',path);mod=importlib.util.module_from_spec(sp);sp.loader.exec_module(mod)
def fixture(generation,total=1):
    b=bytearray(b'\xff'*4096);b[:8]=b'BPROLOG3'
    struct.pack_into('<5I',b,8,3,generation,1,20000,total)
    first=min(total,24);last=min(max(total-24,0),24)
    struct.pack_into('<2H3I',b,28,first,last,1,(first+last)*72,0xf0000)
    b[64:128]=bytes(64);b[64:69]=b'BCAP\3'
    times=list(range(first))+list(range(max(first,total-last),total))
    for i,t in enumerate(times):
        at=128+i*72;b[at:at+72]=bytes(72);struct.pack_into('<I',b,at,t)
        b[at+4]=2;b[at+8:at+10]=b'\x80\x02'
    struct.pack_into('<I',b,4092,zlib.crc32(b[:4092]));return bytes(b)
def bad(blob):
    try:mod.decode_slots(blob)
    except ValueError:return
    raise AssertionError('Corrupt data accepted')
good=fixture(1)
assert mod.decode_slots(good)['newest']['generation']==1
bad(bytes(4096));bad(good[:2048]);bad(good[:100]+bytes([good[100]^1])+good[101:])
assert mod.decode_slots(good+fixture(2))['newest']['generation']==2
assert mod.decode_slots(good+bytes(4096))['newest']['generation']==1
partial=fixture(2)[:512]+b'\xff'*(4096-512)
assert mod.decode_slots(good+partial)['newest']['generation']==1
assert mod.decode_slots(fixture(0xffffffff)+fixture(0))['newest']['generation']==0
assert mod.decode_slots(fixture(8,100))['newest']['dropped_middle_events']==52
print('9 capture format checks passed; no devices opened')
