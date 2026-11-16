import unittest
from ram_pacing_loop import PhaseObserver,poll_window
from test_ram_retention_loop import Client

class PacingTests(unittest.TestCase):
    def test_phase_separation_and_same_pause(self):
        t=[0.];pauses=[];c=Client();o=PhaseObserver()
        def poll():t[0]+=.002;return dict(events=[],flags=1)
        def pause(n):pauses.append(n);t[0]+=.010
        c.poll=poll
        r=poll_window(c,o,lambda:t[0],pause,seconds=.024)
        self.assertEqual(r['poll_calls'],2);self.assertEqual(pauses,[.004,.004])
        for row in o.rows:
            self.assertAlmostEqual(row['poll_end']-row['poll_start'],.002)
            self.assertAlmostEqual(row['sleep_end']-row['sleep_start'],.010)
    def test_capacity_stops_before_another_poll(self):
        t=[0.];c=Client();o=PhaseObserver(1)
        with self.assertRaisesRegex(ValueError,'capacity'):
            poll_window(c,o,lambda:t[0],lambda n:t.__setitem__(0,t[0]+n),seconds=.02)
        self.assertEqual(c.calls,1)
    def test_query_limit(self):
        c=Client()
        with self.assertRaisesRegex(ValueError,'query bound'):
            poll_window(c,PhaseObserver(),lambda:0.,lambda n:None,maximum_queries=2)
        self.assertEqual(c.calls,2)
    def test_terminal_and_events_stop_without_sleep(self):
        for frame in [dict(events=[1],flags=1),dict(events=[],flags=9)]:
            with self.assertRaisesRegex(ValueError,'Unexpected'):
                poll_window(Client(frame),PhaseObserver(),lambda:0.,lambda n:self.fail('slept'))
    def test_clock_reversal_inside_poll(self):
        t=[1.];c=Client()
        def poll():t[0]=.5;return dict(events=[],flags=1)
        c.poll=poll
        with self.assertRaisesRegex(ValueError,'reversed'):
            poll_window(c,PhaseObserver(),lambda:t[0],lambda n:None)
    def test_no_replies_rejected(self):
        t=[0.];c=Client();c.poll=lambda:None
        with self.assertRaisesRegex(ValueError,'No valid'):
            poll_window(c,PhaseObserver(),lambda:t[0],lambda n:t.__setitem__(0,t[0]+n),seconds=.004)
    def test_observer_records_cost(self):
        o=PhaseObserver();clock=iter([1.,1.002])
        o.record({},lambda:next(clock));self.assertAlmostEqual(o.maximum_cost,.002)

if __name__=='__main__':unittest.main()
