import os,types,unittest
from unittest.mock import Mock
import sustained_game_spin_child as source
from offline_spin_adapter import SpinTime

class Tests(unittest.TestCase):
    def test_reuses_actual_code_without_environment_or_shared_state_mutation(self):
        before_env=dict(os.environ);before_stats=source.spin_stats()
        clock=Mock(side_effect=[10.,10.,10.00025,10.0005,10.00075]);sleep=Mock()
        adapter=SpinTime(types.SimpleNamespace(perf_counter=clock,sleep=sleep),
            lambda:types.SimpleNamespace(target=10.0005))
        self.assertIs(adapter.wait.__code__,source.wait.__code__)
        adapter.sleep(.001)
        sleep.assert_not_called()
        self.assertEqual(adapter.summary()['spins'],1)
        self.assertEqual(source.spin_stats(),before_stats)
        self.assertEqual(dict(os.environ),before_env)

    def test_other_sleep_calls_not_replaced(self):
        sleep=Mock();clock=Mock()
        adapter=SpinTime(types.SimpleNamespace(perf_counter=clock,sleep=sleep),lambda:None)
        adapter.sleep(.01);adapter.sleep(.08)
        self.assertEqual([c.args for c in sleep.call_args_list],[(.01,),(.08,)])
        clock.assert_not_called()

    def test_prearm_keeps_one_ms_sleep(self):
        sleep=Mock();clock=Mock()
        adapter=SpinTime(types.SimpleNamespace(perf_counter=clock,sleep=sleep),lambda:None)
        adapter.sleep(.001)
        sleep.assert_called_once_with(.001);clock.assert_not_called()

if __name__=='__main__':unittest.main()
