import ast,pathlib,unittest
from bridge_desktop import cancel_path,PRIVATE
ROOT=pathlib.Path(__file__).resolve().parents[1]
class Tests(unittest.TestCase):
    def test_cancel_session_path_scoped(self):self.assertEqual(cancel_path('20261030-120000').parent,PRIVATE)
    def test_path_traversal_and_malformed_rejected(self):
        for value in ('../other','20261030-120000/../x','','any-session'):
            with self.assertRaises(ValueError):cancel_path(value)
    def test_gui_has_no_forced_process_kill(self):
        tree=ast.parse((ROOT/'tools/bridge_desktop.py').read_text(encoding='utf-8'))
        self.assertFalse(any(isinstance(n,ast.Attribute) and n.attr in ('kill','terminate') for n in ast.walk(tree)))
if __name__=='__main__':unittest.main()
