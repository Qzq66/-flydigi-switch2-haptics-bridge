import unittest
from dispatch_failure_analysis import inject_delay
class Tests(unittest.TestCase):
    def test_file_write_delay_can_trigger_without_heartbeat_loss(self):
        r=inject_delay('phase_file_write',.005);self.assertIn('scheduler late',r['fault']);self.assertLess(r['heartbeat_age_seconds'],.08);self.assertEqual(r['frames'],0);self.assertEqual(r['stops'],1)
    def test_queue_processing_delay_can_trigger(self):
        r=inject_delay('inbox_drain',.005);self.assertIn('scheduler late',r['fault']);self.assertEqual(r['stops'],1)
    def test_wakeup_delay_can_trigger(self):
        r=inject_delay('sleep_overshoot',.005);self.assertIn('scheduler late',r['fault']);self.assertEqual(r['mode_enables'],1)
    def test_slow_writer_causes_next_deadline_failure_without_catchup(self):
        r=inject_delay('writer_block',.013);self.assertIn('scheduler late',r['fault']);self.assertEqual(r['frames'],1);self.assertEqual(r['stops'],1);self.assertFalse(r['output_dirty'])
    def test_three_ms_delay_does_not_relax_threshold(self):
        r=inject_delay('phase_file_write',.003);self.assertIsNone(r['fault']);self.assertEqual(r['frames'],1)
if __name__=='__main__':unittest.main()
