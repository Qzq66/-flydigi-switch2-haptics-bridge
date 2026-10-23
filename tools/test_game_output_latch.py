"""Prompt-cap muting keeps input transport available without restarting output."""
import pathlib,sys,unittest
from unittest.mock import Mock
sys.path.insert(0,str(pathlib.Path(__file__).absolute().parents[1]/'handoff/2026-10-22/work'))
from bridge_render import GameOutputLatch
from bridge_protocol import BridgeFault

class Latch(unittest.TestCase):
    def make(self,why='calibrated prompt count cap',stop=None):
        r=Mock();r.last_received=0;r.block.side_effect=BridgeFault(why)
        stop=stop or Mock();return r,stop,GameOutputLatch(r,stop)
    def test_cap_stops_once_and_never_sends_more(self):
        r,stop,p=self.make();self.assertIsNone(p.block(0));stop.assert_called_once()
        for n in range(1,100):
            p.feed(dict(flags=3,received_at=n/100));self.assertIsNone(p.block(n/100))
        r.block.assert_called_once();r.feed.assert_not_called();stop.assert_called_once()
        self.assertEqual(p.reason,'calibrated prompt count cap')
    def test_muted_heartbeat_and_usb_loss_remain_faults(self):
        r,stop,p=self.make();p.block(0)
        with self.assertRaisesRegex(BridgeFault,'heartbeat'):p.block(.081)
        with self.assertRaisesRegex(BridgeFault,'USB'):p.feed(dict(flags=1,received_at=.01))
    def test_other_faults_are_not_muted(self):
        for why in ('wire heartbeat timeout','unknown decoder state','first-test active energy duration cap'):
            with self.subTest(why=why):
                r,stop,p=self.make(why)
                with self.assertRaisesRegex(BridgeFault,why):p.block(0)
                stop.assert_not_called();self.assertIsNone(p.reason)
    def test_failed_stop_propagates(self):
        stop=Mock(side_effect=RuntimeError('stop failed'));r,stop,p=self.make(stop=stop)
        with self.assertRaisesRegex(RuntimeError,'stop failed'):p.block(0)
        self.assertIsNone(p.reason)
    def test_slow_stop_does_not_restart_pcm_clock(self):
        r,stop,p=self.make();p.block(0)
        # Transport continues publishing current heartbeats after a slow ACK.
        # Muted blocks never call the failed renderer or generate catch-up PCM.
        p.feed(dict(flags=3,received_at=.250))
        self.assertIsNone(p.block(.254));r.block.assert_called_once()
        stop.assert_called_once()

if __name__=='__main__':unittest.main()
