"""Real decoder/rendering stays silent before arming, without spending its budget."""
import pathlib,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).absolute().parents[1]/'handoff/2026-10-22/work'))
from bridge_render import Renderer,phase_frame
from bridge_protocol import BridgeFault

class Phase(unittest.TestCase):
    def test_prearm_four_pulses_silent_then_one_real_pulse(self):
        r=Renderer(prompt_ms=120,prompt_offset=12,game_pilot=True)
        neutral=bytes.fromhex('0001404000014040');pulse=bytes.fromhex('801860b200000000')
        r.feed(phase_frame(dict(source_us=0,received_at=0,flags=7,events=[]),False))
        for i in range(190):
            source=i*8;now=(64+source)/1000;armed=source>=1000
            raw=pulse if source in (0,200,400,600,1000) else neutral
            frame=dict(source_us=(64+source)*1000,received_at=now,processed_at=now,flags=7,events=[dict(at_us=source*1000,motors=raw)])
            r.feed(phase_frame(frame,armed));pcm=r.block(now)
            if not armed:
                self.assertEqual(r.prompt_counts,[0,0]);self.assertEqual(pcm,[[128]*8,[128]*8])
        self.assertEqual(r.prompt_counts,[1,0]);self.assertEqual(r.active_total,[120,0])
    def test_mask_retains_inputs_events_and_does_not_mutate_original(self):
        frame=dict(flags=7,events=[dict(motors=b'12345678')],source_us=1)
        masked=phase_frame(frame,False);self.assertEqual(masked['flags'],3);self.assertEqual(frame['flags'],7)
        self.assertIs(masked['events'],frame['events']);self.assertIs(phase_frame(frame,True),frame)
    def test_prearm_heartbeat_fault_still_applies(self):
        r=Renderer(prompt_ms=120,game_pilot=True);r.feed(phase_frame(dict(flags=7,received_at=0,source_us=0,events=[]),False))
        with self.assertRaisesRegex(BridgeFault,'heartbeat'):r.block(.081)

if __name__=='__main__':unittest.main()
