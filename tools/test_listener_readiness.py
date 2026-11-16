"""A spawned process alone must never authorize the USB-swap instruction."""
import json,unittest
from unittest.mock import Mock
from listener_readiness import wait_for_discovery

class Readiness(unittest.TestCase):
    def phase(self,state='DISCOVERING',clock='monotonic'):
        p=Mock();p.read_text.return_value=json.dumps(dict(phase=state,clock=clock));return p
    def test_requires_post_neutral_phase(self):
        proc=Mock();proc.poll.return_value=None
        wait_for_discovery(proc,self.phase(),clock=Mock(side_effect=[0,0]))
        self.assertEqual(proc.poll.call_count,2)
    def test_early_exit_never_reports_ready(self):
        proc=Mock();proc.poll.return_value=1
        with self.assertRaisesRegex(RuntimeError,'exited'):wait_for_discovery(proc,self.phase(),clock=Mock(side_effect=[0,0]))
    def test_exit_during_ready_read_is_rejected(self):
        proc=Mock();proc.poll.side_effect=[None,1]
        with self.assertRaisesRegex(RuntimeError,'exited'):wait_for_discovery(proc,self.phase(),clock=Mock(side_effect=[0,0]))
    def test_missing_unready_or_wrong_clock_times_out(self):
        for p in (self.phase('INPUT_READY'),self.phase(clock='perf_counter'),self.phase('WAITING'),Mock()):
            if not isinstance(p.read_text.return_value,str):p.read_text.side_effect=FileNotFoundError()
            proc=Mock();proc.poll.return_value=None
            with self.assertRaises(TimeoutError):wait_for_discovery(proc,p,clock=Mock(side_effect=[0,0,16]),pause=lambda _:None)
    def test_partial_json_is_not_ready(self):
        proc=Mock();proc.poll.return_value=None;p=Mock();p.read_text.return_value='{'
        with self.assertRaises(TimeoutError):wait_for_discovery(proc,p,clock=Mock(side_effect=[0,0,16]),pause=lambda _:None)

if __name__=='__main__':unittest.main()
