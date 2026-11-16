import copy,json,pathlib,tempfile,types,unittest
from unittest.mock import patch
import startup_current_config_owner as candidate
class Tests(unittest.TestCase):
    def setUp(self):
        selection=json.loads((candidate.PRIVATE/'startup-config-selection-2026-11-15.json').read_text());self.expected=json.loads(pathlib.Path(selection['current_configuration_backup']).read_text());self.data=copy.deepcopy(self.expected)
        self.owner=types.SimpleNamespace(safe=types.SimpleNamespace(digest=lambda v:self.data['identity_sha256'],read_ram=lambda r,i:(bytes.fromhex(self.data['ram'][{1:'global',4:'mapping',5:'lighting',6:'motors'}[i]]['raw_hex']),{})),identity=lambda r,b:None)
        self.reader=types.SimpleNamespace(ask=lambda *a,**k:b'',state=lambda:self.data['state'])
    def backup(self):
        with patch('bridge_windows.load_owner',return_value=self.owner):o=candidate.load_owner()
        with tempfile.TemporaryDirectory() as d:return o.backup(self.reader,pathlib.Path(d)/'backup.json')
    def test_exact_current_configuration_passes(self):self.assertEqual(self.backup()['state_before'],self.expected['state'])
    def test_identity_change_rejected(self):
        self.data['identity_sha256']='changed'
        with self.assertRaises(ValueError):self.backup()
    def test_state_change_rejected(self):
        self.data['state'][1]+=1
        with self.assertRaises(ValueError):self.backup()
    def test_each_ram_region_change_rejected(self):
        for label in ('global','mapping','lighting','motors'):
            with self.subTest(label=label):
                self.data=copy.deepcopy(self.expected);raw=bytearray.fromhex(self.data['ram'][label]['raw_hex']);raw[-1]^=1;self.data['ram'][label]['raw_hex']=raw.hex()
                with self.assertRaises(ValueError):self.backup()
    def test_only_read_methods_used(self):self.backup() # fake exposes no mode/stream/write method
if __name__=='__main__':unittest.main()
