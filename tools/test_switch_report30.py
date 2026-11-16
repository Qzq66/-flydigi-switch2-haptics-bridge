import unittest
from switch_report30 import decode, require_neutral


class Report30Tests(unittest.TestCase):
    def test_published_stick_example(self):
        p = bytearray(49); p[0] = 0x30; p[6:9] = bytes.fromhex('fd877b')
        r = decode(p)
        self.assertEqual((r['lx'], r['ly']), (2045, 1976))

    def test_face_buttons_independent(self):
        for value, expected in ((1, 'y'), (2, 'x'), (4, 'b'), (8, 'a')):
            p = bytearray(64); p[0] = 0x30; p[3] = value
            r = decode(p)
            self.assertEqual([x for x in ('a', 'b', 'x', 'y') if r[x]], [expected])

    def test_axes_bounds_and_nibble_split(self):
        p = bytearray(64); p[0] = 0x30
        p[6:9] = bytes.fromhex('ff0f00'); p[9:12] = bytes.fromhex('00f0ff')
        r = decode(p)
        self.assertEqual((r['lx'], r['ly'], r['rx'], r['ry']), (4095, 0, 0, 4095))

    def test_reject_truncated_wrong_id_and_oversize(self):
        for data in (b'', b'\x30'*48, b'\x3f'+bytes(63), b'\x30'+bytes(64)):
            with self.assertRaises(ValueError): decode(data)

    def test_padding_does_not_change_fields(self):
        p = bytearray(49); p[0] = 0x30; p[3] = 12
        self.assertEqual(decode(p), decode(p+bytes(15)))

    def neutral_packet(self):
        p = bytearray(64); p[0] = 0x30; p[4] = 0x80
        p[6:9] = bytes.fromhex('088880'); p[9:12] = bytes.fromhex('088880')
        return p

    def test_observed_status_bit_is_not_a_button(self):
        r = decode(self.neutral_packet())
        self.assertEqual((r['misc_buttons'], r['misc_active_buttons'], r['misc_status_bits']), (128, 0, 128))
        require_neutral([r])

    def test_real_buttons_and_unknown_status_still_block(self):
        for offset, mask in ((3, 8), (3, 4), (4, 2), (4, 16), (5, 64), (4, 64)):
            p = self.neutral_packet(); p[offset] |= mask
            with self.assertRaises(ValueError): require_neutral([decode(p)])

    def test_stick_guard_unchanged(self):
        p = self.neutral_packet(); p[6:9] = b'\0\0\0'
        with self.assertRaises(ValueError): require_neutral([decode(p)])


if __name__ == '__main__':
    unittest.main()
