import unittest
from switch_rumble_packet import report, validate


class PacketTests(unittest.TestCase):
    def test_neutral_matches_protocol_vector(self):
        self.assertEqual(report(0).hex(), '10000001404000014040' + '00'*54)

    def test_low_vector_and_independent_sides(self):
        self.assertEqual(report(15, True, False)[:10].hex(), '100f801ac04600014040')
        self.assertEqual(report(3, False, True)[:10].hex(), '100300014040801ac046')
        self.assertEqual(report(2, True, True)[:10].hex(), '1002801ac046801ac046')

    def test_reject_unbounded_parameters(self):
        for value in (-1, 16, True, 1.5):
            with self.assertRaises(ValueError): report(value)
        with self.assertRaises(ValueError): report(0, 255)

    def test_reject_configuration_or_unreviewed_payload(self):
        for offset in (0, 1, 2, 6, 10, 63):
            p = bytearray(report(0)); p[offset] = 255
            with self.assertRaises(ValueError): validate(p)
        for p in (b'', report(0)[:-1], report(0)+b'\0'):
            with self.assertRaises(ValueError): validate(p)

    def test_validate_all_allowed_states(self):
        for sequence in range(16):
            for left in (False, True):
                for right in (False, True):
                    p = report(sequence, left, right)
                    self.assertEqual(validate(p), p)


if __name__ == '__main__':
    unittest.main()
