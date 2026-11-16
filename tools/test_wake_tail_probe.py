"""Synthetic tests for the wake-tail probe helpers (no Win32 calls)."""
import pathlib, tempfile, unittest
import wake_tail_probe as probe


class Tests(unittest.TestCase):
    def test_summarize_counts_thresholds(self):
        arm = probe.summarize([.001, .005, .007], [.0005, .0035, .006])
        self.assertEqual(arm['periods_over_4ms'], 2)
        self.assertEqual(arm['periods_over_6ms'], 1)
        self.assertEqual(arm['overshoots_over_1ms'], 2)
        self.assertEqual(arm['overshoots_over_3ms'], 2)
        self.assertEqual(arm['overshoots_over_5ms'], 1)

    def test_composed_loop_composition(self):
        seen = []
        def wait(seconds):
            seen.append(seconds)
        with tempfile.TemporaryDirectory() as tmp:
            periods, overshoots = probe.composed_loop(wait, 5, pathlib.Path(tmp))
            self.assertEqual(len(seen), 5)
            self.assertEqual(len(overshoots), 5)
            self.assertEqual(len(periods), 4)
            self.assertTrue(all(isinstance(value, float) for value in overshoots))
            self.assertTrue((pathlib.Path(tmp) / 'composed.phase').exists())

    def test_composed_loop_refuses_cancel_marker(self):
        def wait(seconds):
            pass
        with tempfile.TemporaryDirectory() as tmp:
            (pathlib.Path(tmp) / 'composed.cancel').write_text('cancel')
            with self.assertRaises(RuntimeError):
                probe.composed_loop(wait, 3, pathlib.Path(tmp))

    def test_arm_names_match_documentation(self):
        self.assertEqual(probe.THREAD_PRIORITY_TIME_CRITICAL, 15)
        self.assertEqual(probe.CREATE_WAITABLE_TIMER_HIGH_RESOLUTION, 0x2)


if __name__ == '__main__':
    unittest.main()
