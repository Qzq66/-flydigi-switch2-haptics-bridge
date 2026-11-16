"""Synthetic boundary checks for gap decomposition; no device or network."""
import unittest
from analyse_pcm_postmute_gap import decompose,window
class GapTests(unittest.TestCase):
 def rows(self):
  return [dict(kind='frame',at=1.,duration=.002,gap=.015,source_us=1000000),dict(kind='timeout',at=1.072,duration=.060),dict(kind='frame',at=1.100,duration=.011,gap=.100,source_us=1090000)]
 def test_real_adjacent_decomposition(self):
  r=decompose(self.rows());self.assertTrue(r['available'])
  for k,v in [('receive_gap_ms',100),('before_timeout_poll_ms',12),('timeout_poll_ms',60),('timeout_end_to_next_receive_ms',28),('post_timeout_to_next_poll_start_lower_ms',17),('heartbeat_margin_at_timeout_return_ms',8),('next_poll_start_beyond_heartbeat_deadline_lower_ms',9)]:self.assertAlmostEqual(r[k],v)
 def test_lower_bound_is_not_actual_sleep(self):
  r=decompose(self.rows());actual=(1.101-.011-1.072)*1000
  self.assertLess(r['post_timeout_to_next_poll_start_lower_ms'],actual);self.assertTrue(r['lower_bound_is_not_measured_sleep'])
 def test_missing_predecessor(self):self.assertFalse(decompose(self.rows()[-1:])['available'])
 def test_subset_neighbour_not_original(self):
  rows=self.rows();rows[-1]['gap']=.020;self.assertFalse(decompose(rows)['available'])
 def test_multiple_or_missing_timeouts(self):
  rows=self.rows();self.assertFalse(decompose([rows[0],rows[-1]])['available']);rows.insert(2,dict(kind='timeout',at=1.08,duration=.008));self.assertFalse(decompose(rows)['available'])
 def test_source_clock_wrap_interval_only(self):
  rows=self.rows();rows[0]['source_us']=0xfffffff0;rows[-1]['source_us']=0x20;r=decompose(rows);self.assertAlmostEqual(r['accepted_board_timestamp_gap_ms'],.048);self.assertFalse(r['board_and_pc_absolute_clocks_synchronised'])
 def test_reversed_snapshot_rejected(self):
  s=dict(recent=list(reversed(self.rows())),maximum_response_gap_seconds=.1,poll_calls=3,responses=2,timeouts=1,observed_boot_ids=[0])
  with self.assertRaises(ValueError):window(s)
 def test_nonatomic_counter_residual(self):
  s=dict(recent=self.rows(),maximum_response_gap_seconds=.1,poll_calls=4,responses=2,timeouts=1,observed_boot_ids=[0]);r=window(s);self.assertEqual(r['calls_minus_responses_and_timeouts'],1);self.assertFalse(r['snapshots_are_atomic'])
if __name__=='__main__':unittest.main()
