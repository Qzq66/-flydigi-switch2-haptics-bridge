import hashlib,struct,unittest
from forensic_wifi_decode import known_wifi_payload
from test_component_receive_analysis import reply
from test_pktmon_capture import capture
from pcapng_experiment import packets

def wifi(payload,qos=True,four=False,ordered=False,amsdu=False):
    ethernet=list(packets(capture(payload)))[0]['data']
    control=0x0088 if qos else 0x0008
    if four:control|=0x0300
    if ordered:control|=0x8000
    header=struct.pack('<H',control)+b'\0'*22
    if four:header+=b'\0'*6
    if qos:header+=bytes([0x80 if amsdu else 0,0])
    if qos and ordered:header+=b'\0'*4
    return header+b'\xaa\xaa\x03\0\0\0\x08\0'+ethernet[14:]

class WifiEvidenceTests(unittest.TestCase):
    def setUp(self):self.p=reply();self.expected={hashlib.sha256(self.p).hexdigest()}
    def test_plain_and_qos(self):
        for qos in (True,False):self.assertEqual(known_wifi_payload(wifi(self.p,qos),self.expected),self.p)
    def test_four_addresses_and_ordered_qos(self):
        self.assertEqual(known_wifi_payload(wifi(self.p,four=True,ordered=True),self.expected),self.p)
    def test_unknown_hash_rejected(self):self.assertIsNone(known_wifi_payload(wifi(self.p),set()))
    def test_corrupted_crc_rejected_even_if_hash_whitelisted(self):
        bad=self.p[:-1]+b'X';self.assertIsNone(known_wifi_payload(wifi(bad),{hashlib.sha256(bad).hexdigest()}))
    def test_bad_llc_and_embedded_magic_not_scanned(self):
        d=bytearray(wifi(self.p));d[26]=0
        self.assertIsNone(known_wifi_payload(bytes(d),self.expected))
    def test_aggregation_and_fragment_rejected(self):
        self.assertIsNone(known_wifi_payload(wifi(self.p,amsdu=True),self.expected))
        d=bytearray(wifi(self.p));d[1]|=4
        self.assertIsNone(known_wifi_payload(bytes(d),self.expected))
    def test_truncated_frame(self):self.assertIsNone(known_wifi_payload(wifi(self.p)[:-1],self.expected))
    def test_no_decryption_attempt(self):
        self.assertIsNone(known_wifi_payload(b'\x88\x40'+b'\x55'*120,self.expected))

if __name__=='__main__':unittest.main()
