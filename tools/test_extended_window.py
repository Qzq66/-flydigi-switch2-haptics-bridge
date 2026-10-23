"""Offline duration contracts and complete-capacity journal termination."""
import json,pathlib,struct,sys,unittest,zlib,re
ROOT=pathlib.Path(__file__).absolute().parents[1];sys.path.insert(0,str(ROOT/'handoff/2026-10-22/work'))
from bridge_session_policy import session_limits
from pico_continuous_log import SLOT,CAPACITY,decode_sector

def fixture(total=CAPACITY,reason=3):
    b=bytearray(SLOT);b[:8]=b'BPROLOG5';n=min(total,CAPACITY);overflow=total>n
    struct.pack_into('<5I2H6I',b,8,5,11,reason,20000,total,n,24,1|(2 if overflow else 0),n*24,0xe0000,CAPACITY,100 if overflow else 0xffffffff,1000000)
    b[56:60]=b'END2';struct.pack_into('<I',b,60,1);b[64:69]=b'BCAP\x05'
    for i in range(n):
        at=128+i*24;struct.pack_into('<II',b,at,i*100,i);b[at+8]=0x10;b[at+9]=10;b[at+20]=1
    struct.pack_into('<I',b,SLOT-4,zlib.crc32(b[:-4]));return b

class Duration(unittest.TestCase):
    def test_baseline_unchanged(self):
        v=session_limits(60);self.assertEqual((v['host_live_seconds'],v['guardian_seconds'],v['arm_latest_seconds'],v['ui_deadline_seconds']),(62,200,55,58))
    def test_extended_limits_cover_discovery_live_and_cleanup(self):
        v=session_limits(120);self.assertEqual(v['expected_firmware'],'v043')
        self.assertGreater(v['guardian_seconds'],v['discovery_seconds']+v['host_live_seconds']+20)
        self.assertLess(v['arm_latest_seconds'],v['ui_deadline_seconds']);self.assertLess(v['ui_deadline_seconds'],120)
    def test_invalid_duration_rejected(self):
        for value in (True,60.0,0,59,121,600):
            with self.subTest(value=value),self.assertRaises(ValueError):session_limits(value)
    def test_firmware_has_end_margin_and_distinct_candidate(self):
        header=(ROOT/'handoff/2026-10-22/outputs/pico-haptics-bridge-v043/session_policy.h').read_text()
        values={k:int(v) for k,v in re.findall(r'(BRIDGE_\w+_MS)=(\d+)',header)}
        self.assertEqual(values['BRIDGE_LIVE_MS'],120000)
        self.assertGreater(values['BRIDGE_BOOT_MS'],values['BRIDGE_LIVE_MS'])
        self.assertGreater(values['BRIDGE_REBOOT_MS'],values['BRIDGE_BOOT_MS']+8000)

class Capacity(unittest.TestCase):
    def test_full_log_keeps_last_motor_word_and_marks_early_end(self):
        d=decode_sector(fixture());self.assertTrue(d['complete']);self.assertEqual(d['reason'],'capacity_limit')
        self.assertEqual(d['stored_events'],CAPACITY);self.assertEqual(d['events'][-1]['sequence'],CAPACITY-1)
        self.assertEqual(sum(e['motors_hex'] is not None for e in d['events']),CAPACITY)
        self.assertEqual(d['stream_end'],'client_confirmed');self.assertEqual(d['dropped_events'],0)
    def test_capacity_marker_rejects_partial_or_overflow(self):
        for total in (0,CAPACITY-1,CAPACITY+1):
            with self.subTest(total=total),self.assertRaisesRegex(ValueError,'capacity'):decode_sector(fixture(total))
    def test_old_deadline_format_remains_readable(self):
        self.assertEqual(decode_sector(fixture(1,1))['reason'],'capture_deadline')
    def test_unknown_reason_rejected(self):
        with self.assertRaises(ValueError):decode_sector(fixture(1,5))
    def test_boot_limit_requires_persistent_full_boot_deadline(self):
        b=fixture(1,4)
        with self.assertRaisesRegex(ValueError,'boot-limit'):decode_sector(b)
        struct.pack_into('<I',b,20,180100);struct.pack_into('<I',b,SLOT-4,zlib.crc32(b[:-4]))
        self.assertEqual(decode_sector(b)['reason'],'boot_limit')

if __name__=='__main__':unittest.main()
