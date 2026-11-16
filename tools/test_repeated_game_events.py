"""Synthetic-time candidate checks; no USB, sockets, actuators or wall-clock waits."""
import pathlib,sys,unittest
from types import SimpleNamespace
sys.path.insert(0,str(pathlib.Path(__file__).absolute().parents[1]/'handoff/2026-10-22/work'))
from bridge_render import Renderer,GameOutputLatch,phase_frame
from bridge_input import convert,NEUTRAL
from bridge_protocol import BridgeFault

NEUTRAL_WORD=bytes.fromhex('00014040')
ACTIVE_WORD=bytes.fromhex('801860b2')

def simulate(edges,prearm=(),end_ms=7000,disable_at=None):
    renderer=Renderer(prompt_ms=120,prompt_offset=12,game_pilot=True)
    stops=[];latch=GameOutputLatch(renderer,lambda:stops.append(True))
    renderer.feed(dict(source_us=0,received_at=0,flags=7,events=[]))
    maximum=0;outputs=[];inputs=[]
    for source in range(0,end_ms,8):
        now=(source+64)/1000
        armed=source>=1000
        active=source in edges or source in prearm
        word=ACTIVE_WORD if active else NEUTRAL_WORD
        flags=3 if disable_at is not None and source>=disable_at else 7
        frame=dict(source_us=(source+64)*1000,received_at=now,processed_at=now,
            flags=flags,events=[dict(at_us=source*1000,motors=word*2)])
        latch.feed(phase_frame(frame,armed));pcm=latch.block(now)
        if pcm is not None:maximum=max(maximum,max(abs(v-128) for side in pcm for v in side))
        outputs.append((source,pcm))
        # Physical-position input conversion is independent of output state.
        buttons=0x1000 if source%80==0 else 0x2000 if source%80==8 else 0
        inputs.append((source,convert(SimpleNamespace(buttons=buttons,lt=0,rt=0,lx=0,ly=0,rx=0,ry=0))))
    return renderer,latch,stops,maximum,outputs,inputs

class RepeatedGameEvents(unittest.TestCase):
    def test_two_events_five_seconds_apart_complete_and_quiet_between(self):
        r,latch,stops,maximum,output,inputs=simulate((1000,6000))
        self.assertEqual(r.prompt_counts,[2,2]);self.assertEqual(r.active_total,[240,240])
        self.assertEqual(maximum,12);self.assertIsNone(latch.reason);self.assertEqual(stops,[])
        quiet=[pcm for source,pcm in output if 1200<=source<6000 or source>=6200]
        self.assertTrue(quiet);self.assertTrue(all(pcm==[[128]*8,[128]*8] for pcm in quiet))
        self.assertTrue(any(raw!=NEUTRAL for source,raw in inputs if source>=6200))
        self.assertEqual(inputs[-1][1],NEUTRAL)

    def test_prearm_events_spend_no_budget_then_two_complete(self):
        r,latch,stops,maximum,output,_=simulate((1000,6000),prearm=(0,200,400,600))
        self.assertEqual(r.prompt_counts,[2,2]);self.assertEqual(r.active_total,[240,240])
        self.assertTrue(all(pcm==[[128]*8,[128]*8] for source,pcm in output if source<1000))

    def test_fourth_event_mutes_once_with_input_conversion_continuing(self):
        r,latch,stops,maximum,output,inputs=simulate((1000,2000,3000,4000))
        self.assertEqual(r.prompt_counts,[3,3]);self.assertEqual(r.active_total,[360,360])
        self.assertEqual(latch.reason,'calibrated prompt count cap');self.assertEqual(stops,[True])
        self.assertEqual(maximum,12)
        self.assertTrue(all(pcm is None for source,pcm in output if source>=4000))
        self.assertTrue(any(raw!=NEUTRAL for source,raw in inputs if source>=5000))
        self.assertEqual(inputs[-1][1],NEUTRAL)
        with self.assertRaisesRegex(BridgeFault,'heartbeat'):latch.block(8)
        with self.assertRaisesRegex(BridgeFault,'USB'):latch.feed(dict(flags=1,received_at=8))

    def test_disable_cancels_pulse_and_does_not_resume_on_heartbeats(self):
        r,latch,stops,maximum,output,_=simulate((1000,),disable_at=1040,end_ms=3000)
        self.assertEqual(r.prompt_counts,[1,1]);self.assertEqual(r.active_total,[40,40])
        self.assertEqual(r.prompt_remaining,[0,0])
        self.assertTrue(all(pcm==[[128]*8,[128]*8] for source,pcm in output if source>=1040))

if __name__=='__main__':unittest.main()
