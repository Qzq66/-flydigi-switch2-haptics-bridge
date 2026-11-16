import ast,copy,unittest
from passive_transport_policy import ROOT,PassiveSession,collection_completed,build_plan,validate_plan

def frame(at=0,sequence=0,flags=7):
    return dict(received_at=at,source_us=round(at*1e6),flags=flags,
        events=[dict(sequence=sequence,at_us=round(at*1e6),motors=b'12345678')])

class Passive(unittest.TestCase):
    def test_plan_requires_fixed_neutral_and_no_actuator(self):
        p=build_plan();validate_plan(p)
        self.assertEqual(p['motor_commands'],0);self.assertEqual(p['input_forwarding'],'fixed_neutral')
        altered=copy.deepcopy(p);altered['motor_commands']=1
        with self.assertRaises(ValueError):validate_plan(altered)

    def test_stall_observed_but_collection_continues_to_end(self):
        session=PassiveSession();session.feed(frame());session.tick(.081);session.tick(.2)
        session.feed(frame(.3,1));session.tick(.4);session.feed(frame(.5,2,25))
        self.assertEqual(len(session.gaps),2);self.assertTrue(session.terminal)
        self.assertEqual(len(session.events),3);self.assertEqual(session.summary()['output_frames'],0)

    def test_gap_at_80ms_does_not_trigger(self):
        session=PassiveSession();session.feed(frame());session.tick(.080)
        self.assertEqual(session.gaps,[])

    def test_gap_history_is_bounded(self):
        session=PassiveSession()
        for n in range(100):session.feed(frame(n,n));session.tick(n+.1)
        self.assertEqual(len(session.gaps),64);self.assertEqual(len(session.events),100)

    def test_sequence_gap_and_bad_word_are_rejected(self):
        for bad in (dict(sequence=1,at_us=0,motors=b'12345678'),dict(sequence=0,at_us=0,motors=b'bad')):
            f=frame();f['events']=[bad]
            with self.assertRaises(ValueError):PassiveSession().feed(f)

    def test_archive_is_complete_up_to_limit_and_never_silently_drops(self):
        session=PassiveSession()
        for n in range(2725):session.feed(frame(n,n))
        self.assertEqual(len(session.events),2725)
        with self.assertRaises(ValueError):session.feed(frame(2725,2725))

    def test_source_or_receiver_clock_reversal_is_rejected(self):
        for field in ('received_at','source_us'):
            session=PassiveSession();session.feed(frame(1));f=frame(2,1);f[field]=0
            with self.assertRaises(ValueError):session.feed(f)

    def test_terminal_and_time_and_zero_output_are_required(self):
        good=dict(motor_commands=0,output_frames=0,terminal_observed=True,terminal_ack_replied=True,collector_ended=True,
            timer_released=True,live_elapsed_seconds=120,events=[{}])
        self.assertTrue(collection_completed(good))
        for key,value in dict(motor_commands=1,output_frames=1,terminal_observed=False,terminal_ack_replied=False,
            collector_ended=False,timer_released=False,live_elapsed_seconds=60,events=[],error='timeout',finalization_errors=['close']).items():
            self.assertFalse(collection_completed(dict(good,**{key:value})),key)

    def test_entry_has_no_actuator_calls_or_renderer(self):
        source=(ROOT/'tools/run_passive_transport.py').read_text(encoding='utf-8');tree=ast.parse(source)
        calls={n.func.attr for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)}
        self.assertFalse(calls.intersection({'mode','stream','waveform','stop','arm'}))
        self.assertNotIn('GameSession',source);self.assertNotIn('StreamSession',source)

if __name__=='__main__':unittest.main()
