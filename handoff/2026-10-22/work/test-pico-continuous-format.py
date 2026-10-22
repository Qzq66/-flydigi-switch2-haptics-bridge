import struct,zlib,json
from pico_continuous_log import SLOT,CAPACITY,decode_slots,decode_sector
checks=[]
def check(name,ok):
    checks.append(dict(name=name,passed=bool(ok)));assert ok,name
def fixture(generation=1,total=3,overflow=None):
    b=bytearray(b'\xff'*SLOT);b[:128]=b'\0'*128;b[:8]=b'BPROLOG5'
    n=min(total,CAPACITY);over=total>n
    struct.pack_into('<5I2H6I',b,8,5,generation,1,20000,total,n,24,1|(2 if over else 0),n*24,0xe0000,CAPACITY,n*100 if over else 0xffffffff,1000000)
    b[64:69]=b'BCAP\x05'
    for i in range(n):
        p=128+i*24;b[p:p+24]=b'\0'*24
        struct.pack_into('<II',b,p,i*100,i);b[p+8]=0x10;b[p+9]=10;b[p+12:p+20]=bytes.fromhex('0001404000014040');b[p+20]=1
    return seal(b)
def seal(b):
    struct.pack_into('<I',b,SLOT-4,zlib.crc32(b[:-4]));return bytes(b)
def invalid(blob):
    try:decode_sector(blob)
    except ValueError:return True
    return False
a=fixture();check('valid_complete',decode_sector(a)['complete'])
check('all_slots_erased_rejected',invalid(b'\xff'*SLOT))
bad=bytearray(a);bad[150]^=1;check('corruption_rejected',invalid(bad))
check('truncated_rejected',invalid(a[:-1]))
check('old_valid_survives_partial_new_slot',decode_slots(a+bytes(bad))['newest']['generation']==1)
check('generation_wrap',decode_slots(fixture(0xffffffff)+fixture(0))['newest']['generation']==0)
over=decode_sector(fixture(total=CAPACITY+5))
check('overflow_flag_and_drop_count',not over['complete'] and over['overflow'] and over['dropped_events']==5)
bad=bytearray(a);struct.pack_into('<I',bad,128+24+4,5)
check('sequence_gap_rejected',invalid(seal(bad)))
bad=bytearray(a);struct.pack_into('<I',bad,128+24,0)
struct.pack_into('<I',bad,128,100)
check('reversed_timestamps_rejected',invalid(seal(bad)))
bad=bytearray(fixture(total=CAPACITY+1));struct.pack_into('<I',bad,32,1)
check('unmarked_overflow_rejected',invalid(seal(bad)))
bad=bytearray(a);bad[128+20]=0
check('missing_motor_flag_rejected',invalid(seal(bad)))
check('capacity_fixture_complete',decode_sector(fixture(total=CAPACITY))['complete'])
for status,label in ((1,'client_confirmed'),(2,'drain_timeout')):
    marked=bytearray(a);marked[56:60]=b'END2';struct.pack_into('<I',marked,60,status)
    check('END2_'+label,decode_sector(seal(marked))['stream_end']==label)
check('legacy_log_has_no_end_claim',decode_sector(a)['stream_end'] is None)
marked=bytearray(a);marked[56:60]=b'END2';struct.pack_into('<I',marked,60,3)
check('invalid_END2_status_rejected',invalid(seal(marked)))
print(json.dumps(checks,indent=2))
