import json
import unittest
from analyse_bt_discovery import analyse

READY = 'BTD1 READY v=1 no_pair=1 storage=ram command=SCAN\nBTD1 PHASE CLASSIC\n'
BLE = 'BTD1 PHASE BLE\n'


def capture(classic='', ble='', reason='complete', ram_errors=0, count=None):
    c, b = classic.count('BTD1 CLASSIC '), ble.count('BTD1 BLE ')
    return (READY + classic + BLE + ble +
        'BTD1 DONE reason=%s classic=%d ble=%d dropped=0 ram_errors=%d ram_writes=2 ram_erases=1\n' %
        (reason, c if count is None else count, b, ram_errors)).encode()


class DiscoveryTests(unittest.TestCase):
    def test_ble_hid_is_only_hint_and_names_addresses_redacted(self):
        result = analyse(capture(ble='BTD1 BLE addr=112233445566 type=1 rssi=-50 data=030312180409426f62\n'))
        self.assertEqual(result['status'], 'COMPLETE')
        self.assertTrue(result['peers'][0]['hid_hint'])
        self.assertFalse(result['identity_verified'])
        self.assertFalse(result['full_services_enumerated'])
        self.assertNotIn('112233445566', json.dumps(result))
        self.assertNotIn('Bob', json.dumps(result))

    def test_unnamed_classic_retained(self):
        r = analyse(capture(classic='BTD1 CLASSIC addr=112233445566 cod=000500 name=-\n'))
        self.assertTrue(r['peers'][0]['peripheral_class_hint'])
        self.assertFalse(r['peers'][0]['name_present'])

    def test_address_updates_merge(self):
        r = analyse(capture(ble='BTD1 BLE addr=112233445566 type=0 rssi=-40 data=-\n' * 2))
        self.assertEqual(len(r['peers']), 1)
        self.assertEqual(r['observations']['BLE'], 2)

    def test_truncated_ad_and_uuid(self):
        for data in ('050941', '020312'):
            with self.subTest(data=data):
                self.assertEqual(analyse(capture(ble='BTD1 BLE addr=112233445566 type=0 rssi=-40 data=%s\n' % data))['status'], 'FAILED')

    def test_incomplete(self):
        self.assertEqual(analyse((READY + BLE).encode())['status'], 'INCOMPLETE')
        self.assertEqual(analyse(capture(reason='cancelled'))['status'], 'INCOMPLETE')

    def test_errors_and_counts(self):
        self.assertEqual(analyse(capture(ram_errors=1))['status'], 'FAILED')
        self.assertEqual(analyse(capture(count=1))['status'], 'FAILED')

    def test_phase_order_and_extra_data(self):
        self.assertEqual(analyse((READY + BLE + BLE).encode())['status'], 'FAILED')
        self.assertEqual(analyse(capture() + b'BTD1 PHASE BLE\n')['status'], 'FAILED')

    def test_size_limit(self):
        with self.assertRaises(ValueError):
            analyse(b'x' * 65537)


if __name__ == '__main__':
    unittest.main()
