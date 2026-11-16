"""Race-free proofs that the spin candidate is the frozen loop with exactly one wait changed."""
import ast, copy, os, pathlib, sys, unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import sustained_game_spin_child as candidate

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _function(path, name):
    tree = ast.parse(path.read_text(encoding='utf-8'))
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError('missing function ' + name)


def _despinned(tree):
    tree = copy.deepcopy(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'wait':
            node.func = ast.Name(id='time', ctx=ast.Load())
            node.func = ast.Attribute(value=ast.Name(id='time', ctx=ast.Load()), attr='sleep', ctx=ast.Load())
            node.args = [ast.Constant(value=.001)]
    return tree


class Tests(unittest.TestCase):
    def setUp(self):
        # Restore caller environment and shared counters, including on assertion failure.
        env = patch.dict(os.environ, {}, clear=False)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop('FLYDIGI_SPIN_WAIT', None)
        stats = patch.dict(candidate._stats, candidate.spin_stats(), clear=True)
        stats.start()
        self.addCleanup(stats.stop)

    def fake_time(self, ticks=()):
        clock = Mock(side_effect=list(ticks))
        sleep = Mock()
        patched = patch.object(candidate, 'time', SimpleNamespace(
            perf_counter=clock, sleep=sleep))
        patched.start()
        self.addCleanup(patched.stop)
        return clock, sleep

    def test_only_the_final_wait_differs(self):
        frozen = _function(ROOT / 'tools/run_sustained_game_g61.py', 'child')
        spun = _function(ROOT / 'tools/sustained_game_spin_child.py', 'child')
        self.assertEqual(ast.dump(_despinned(spun)), ast.dump(frozen))

    def test_disabled_wait_is_the_product_sleep(self):
        clock, sleep = self.fake_time()
        candidate.wait(SimpleNamespace(target=None))
        sleep.assert_called_once_with(.001)
        clock.assert_not_called()

    def test_enabled_wait_sleeps_far_from_deadline(self):
        os.environ['FLYDIGI_SPIN_WAIT'] = '1'
        clock, sleep = self.fake_time([10.0])
        candidate.wait(SimpleNamespace(target=10.05))
        sleep.assert_called_once_with(.001)
        self.assertEqual(clock.call_count, 1)

    def test_enabled_wait_spins_over_the_last_margin(self):
        os.environ['FLYDIGI_SPIN_WAIT'] = '1'
        clock, sleep = self.fake_time([10.0, 10.0, 10.00025, 10.0005, 10.00075])
        before = candidate.spin_stats()
        candidate.wait(SimpleNamespace(target=10.0005))
        sleep.assert_not_called()
        self.assertEqual(clock.call_count, 5)
        after = candidate.spin_stats()
        self.assertEqual(after['spins'], before['spins'] + 1)
        self.assertAlmostEqual(after['spin_seconds'] - before['spin_seconds'], .00075)
        self.assertGreaterEqual(after['maximum_spin_seconds'], .00075 - 1e-12)
        self.assertTrue(after['enabled'])

    def test_missing_target_falls_back_to_sleep(self):
        os.environ['FLYDIGI_SPIN_WAIT'] = '1'
        clock, sleep = self.fake_time()
        candidate.wait(SimpleNamespace())
        sleep.assert_called_once_with(.001)
        clock.assert_not_called()

    def test_none_target_falls_back_to_sleep(self):
        os.environ['FLYDIGI_SPIN_WAIT'] = '1'
        clock, sleep = self.fake_time()
        candidate.wait(SimpleNamespace(target=None))
        sleep.assert_called_once_with(.001)
        clock.assert_not_called()

    def test_expired_target_preserves_existing_sleep_behavior(self):
        os.environ['FLYDIGI_SPIN_WAIT'] = '1'
        for target in (9.0, 10.0):
            with self.subTest(target=target):
                with patch.object(candidate, 'time', SimpleNamespace(
                        perf_counter=Mock(return_value=10.0), sleep=Mock())) as fake:
                    candidate.wait(SimpleNamespace(target=target))
                    fake.sleep.assert_called_once_with(.001)
                    self.assertEqual(fake.perf_counter.call_count, 1)

    def test_only_exact_enable_value_activates_deadline_path(self):
        os.environ['FLYDIGI_SPIN_WAIT'] = '0'
        clock, sleep = self.fake_time()
        candidate.wait(SimpleNamespace(target=10.0))
        sleep.assert_called_once_with(.001)
        clock.assert_not_called()

    def test_margin_is_two_milliseconds(self):
        self.assertEqual(candidate.SPIN_MARGIN, .002)


if __name__ == '__main__':
    unittest.main()
