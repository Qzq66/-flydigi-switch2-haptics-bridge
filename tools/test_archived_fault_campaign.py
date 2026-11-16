import json,pathlib,unittest
from archived_fault_campaign import run_case
ROOT=pathlib.Path(__file__).resolve().parents[1]
class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.events=json.loads((ROOT/'docs/FIDELITY_GAME_RUN_20261115-165425.json').read_text(encoding='utf-8'))['child']['events']
    def check_case(self,name):
        result=run_case(self.events,name)
        self.assertTrue(result['passed'],result)
        self.assertGreater(result['frames_at_fault'],0)
        self.assertEqual(result['stop_calls'],1)
        return result
    def test_dispatch_stall_exact_decision_time_and_no_catchup(self):
        result=self.check_case('dispatch_stall')
        self.assertAlmostEqual(result['first_fault']['lateness_seconds'],.0087)
    def test_heartbeat_timeout_without_dispatch_stall(self):
        result=self.check_case('wire_gap')
        self.assertAlmostEqual(result['first_fault']['lateness_seconds'],0.)
    def test_source_sequence_gap_stops_before_output(self):self.check_case('sequence_gap')
    def test_output_exception_does_not_retry_write(self):self.check_case('output_error')
    def test_collector_exception_stops_before_tick(self):
        result=self.check_case('collector_error')
        self.assertIsNone(result['first_fault']['tick_entry'])
        self.assertEqual(result['raised'],'OSError')
if __name__=='__main__':unittest.main()
