"""Synthetic clocks and real recorded packets; never hardware evidence."""
import json,math,pathlib,unittest
from live_fidelity_candidate import LiveFidelityRenderer,BridgeFault
from haptic_fidelity_candidate import decode_timeline,reconstruct
ROOT=pathlib.Path(__file__).absolute().parents[1]
NEUTRAL=bytes.fromhex('0001404000014040')

def absolute(amp=16,freq=64):return ((1<<30)|(amp<<23)|(freq<<16)|(64<<2)).to_bytes(4,'little')*2
def frame(now,events=(),flags=7,source_us=None):return dict(received_at=now,processed_at=now,source_us=round(now*1e6) if source_us is None else source_us,events=list(events),flags=flags)
def event(seq,at,raw):return dict(sequence=seq,at_us=at,motors=raw)
def ready():
    r=LiveFidelityRenderer();r.feed(frame(0,flags=3));r.arm(0);return r
def synthetic(duration=296,raw=None):
    r=ready();output=[[],[]]
    for seq,source in enumerate(range(0,duration+24,8)):
        now=.064+source/1000;r.feed(frame(now,[event(seq,source*1000,raw or absolute() if source<duration else NEUTRAL)]))
        pcm=r.block(now)
        if pcm is None:break
        for side in (0,1):output[side].extend(pcm[side])
    return r,output

def replay(stamp,delay=0.):
    c=json.loads((ROOT/'docs'/('WINDOWS_V043_GAME_RECHECK_'+stamp+'.json')).read_text())['child']
    anchor=c['source_clock_anchor'];arm_source=anchor['source_us']+(c['armed_at_pc_clock']-anchor['pc_clock'])*1e6
    origin=c['events'][0]['at_us'];arm_pc=(arm_source-origin)/1e6
    events=[dict(sequence=e['sequence'],at_us=e['at_us']-origin,motors=bytes.fromhex(e['motors'])) for e in c['events']]
    r=LiveFidelityRenderer();r.feed(frame(0,flags=3,source_us=0));index=0;packet_us=0
    def feed_until(now):
        nonlocal index,packet_us
        while packet_us/1e6+delay<=now+1e-12:
            batch=[]
            while index<len(events) and events[index]['at_us']<=packet_us:
                batch.append(events[index]);index+=1
            r.feed(dict(received_at=packet_us/1e6+delay,processed_at=now,source_us=packet_us,events=batch,flags=7))
            packet_us+=4000
    feed_until(arm_pc);start=r.arm(arm_pc);pcm=[[],[]]
    for n in range(1900):
        now=start+n*.008;feed_until(now);block=r.block(now)
        if block is None:break
        for side in (0,1):pcm[side].extend(block[side])
    else:raise AssertionError('One episode did not finish within the bounded window')
    # The offline reference uses the same documented group/phase conventions,
    # and independently applies parameters on the 1ms source grid.
    timelines,_=decode_timeline(c['events'],arm_source)
    end=max(c['events'][-1]['at_us'],max(t[-1]['at_us'] for t in timelines))+2000
    reference=reconstruct(timelines,arm_source,end)
    if any(pcm[s]!=reference['pcm'][s][:len(pcm[s])] for s in (0,1)):raise AssertionError('Streaming output differs from offline reconstruction')
    return dict(stamp=stamp,packet_delay_ms=delay*1000,active_ms=r.active_total,peak_code=r.maximum_offset,squared_code_sum=r.dose,blocks=r.blocks,muted_reason=r.muted_reason,offline_prefix_pcm_exact=True)

class Streaming(unittest.TestCase):
    def test_natural_end_matches_independent_offline_model_and_latches_mute(self):
        r,pcm=synthetic();self.assertEqual(r.active_total,[296,296]);self.assertEqual(r.muted_reason,'single bilateral episode completed')
        t=[dict(at_us=0,low_amplitude=2**(-3.9375),low_hz=160.,high_amplitude=0.,high_hz=320.),dict(at_us=296000,low_amplitude=0.,low_hz=160.,high_amplitude=0.,high_hz=320.)]
        reference=reconstruct([t,t],0,len(pcm[0])*1000)
        self.assertEqual(pcm,reference['pcm'])
        r.feed(frame(.4,[event(99,336000,absolute())]));self.assertIsNone(r.block(.4))

    def test_prearm_silent_without_spending_activity_or_energy(self):
        r=LiveFidelityRenderer();r.feed(frame(0,[event(0,0,absolute())]));self.assertEqual(r.block(0),[[128]*8,[128]*8])
        self.assertEqual(r.active_total,[0,0]);self.assertEqual(r.dose,[0,0]);self.assertEqual(r.pending,[])

    def test_arm_requires_fresh_upstream_and_is_one_shot(self):
        with self.assertRaises(BridgeFault):LiveFidelityRenderer().arm(0)
        r=LiveFidelityRenderer();r.feed(frame(0,flags=3))
        with self.assertRaisesRegex(BridgeFault,'heartbeat'):r.arm(.081)
        r=ready()
        with self.assertRaisesRegex(BridgeFault,'one-shot'):r.arm(0)

    def test_heartbeat_usb_loss_and_disabled_source_latch(self):
        for flags in (1,):
            r=ready()
            with self.assertRaisesRegex(BridgeFault,'USB'):r.feed(frame(.01,flags=flags))
        r=ready()
        with self.assertRaisesRegex(BridgeFault,'heartbeat'):r.block(.081)
        r=ready();r.feed(frame(.01,flags=3));self.assertIsNone(r.block(.01))
        r.feed(frame(.02));self.assertIsNone(r.block(.02))

    def test_late_active_and_neutral_are_both_rejected_without_retiming(self):
        for raw in (absolute(),NEUTRAL):
            r=ready()
            with self.assertRaisesRegex(BridgeFault,'deadline'):r.feed(frame(.065,[event(0,0,raw)]))
            with self.assertRaises(BridgeFault):r.block(.066)

    def test_noncontiguous_clock_and_reversed_group_order_fail(self):
        r=ready();r.block(.064);r.feed(frame(.072))
        with self.assertRaisesRegex(BridgeFault,'clock'):r.block(.080)
        r=ready();r.feed(frame(0,[event(0,0,bytes.fromhex('000000c0')*2)]))
        with self.assertRaisesRegex(BridgeFault,'order'):r.feed(frame(.001,[event(1,1000,NEUTRAL)]))

    def test_peak_nyquist_missing_sequence_and_future_time_rejected(self):
        for raw in (absolute(127),absolute(16,127)):
            r=ready()
            with self.assertRaises(BridgeFault):r.feed(frame(0,[event(0,0,raw)]))
        r=ready()
        with self.assertRaisesRegex(BridgeFault,'sequence'):r.feed(frame(0,[event(1,0,NEUTRAL)]))
        r=ready()
        with self.assertRaisesRegex(BridgeFault,'future'):r.feed(frame(0,[event(0,1,NEUTRAL)]))

    def test_duration_and_energy_caps_remain_finite(self):
        with self.assertRaisesRegex(BridgeFault,'320ms'):synthetic(336)
        with self.assertRaisesRegex(BridgeFault,'energy'):synthetic(320,absolute(31))

    def test_real_single_event_traces_match_offline_with_bounded_delay(self):
        for stamp in ('20261024-131624','20261024-132744'):
            for delay in (0.,.016,.032):
                with self.subTest(stamp=stamp,delay=delay):
                    result=replay(stamp,delay);self.assertEqual(result['active_ms'],[296,296]);self.assertLessEqual(max(result['squared_code_sum']),8000)

    def test_beyond_buffer_delay_is_rejected(self):
        with self.assertRaises(BridgeFault):replay('20261024-132744',.072)

    def test_window_limit_and_32bit_source_wrap(self):
        r=ready();r.feed(frame(15.001))
        with self.assertRaisesRegex(BridgeFault,'window'):r.block(15.001)
        r=LiveFidelityRenderer();origin=0xfffff000;r.feed(frame(0,flags=3,source_us=origin));r.arm(0)
        r.feed(frame(.064,[event(0,origin,absolute())],source_us=(origin+64000)&0xffffffff))
        self.assertEqual(len(r.block(.064)[0]),8);self.assertEqual(r.active_total,[8,8])

    def test_queue_capacity_is_bounded(self):
        r=ready();seq=0
        with self.assertRaisesRegex(BridgeFault,'capacity'):
            for batch in range(20):
                events=[event(i,i*15000,bytes.fromhex('000000c0')*2) for i in range(seq,seq+8)];seq+=8
                r.feed(frame(0,events,source_us=events[-1]['at_us']))
        self.assertEqual(r.pending,[])

if __name__=='__main__':unittest.main()
