import unittest
from ram_retention_loop import poll_window

class Client:
    deadline_expirations=late_matching_replies=stale_replies=0
    def __init__(self,frame=None):self.frame=frame if frame is not None else dict(events=[],flags=1);self.calls=0
    def poll(self):self.calls+=1;return self.frame

class RetentionLoopTests(unittest.TestCase):
    def test_bounded_window_no_input_calls(self):
        t=[0.];c=Client()
        def pause(n):t[0]+=n
        r=poll_window(c,lambda:t[0],pause,seconds=.012,maximum_queries=4)
        self.assertTrue(r['completed_window']);self.assertEqual(c.calls,3)
    def test_maximum_queries_stops(self):
        c=Client()
        with self.assertRaisesRegex(ValueError,'bound'):poll_window(c,lambda:0.,lambda n:None,maximum_queries=3)
        self.assertEqual(c.calls,3)
    def test_early_terminal_or_upstream_stops(self):
        for frame in [dict(events=[1],flags=1),dict(events=[],flags=9)]:
            c=Client(frame)
            with self.assertRaises(ValueError):poll_window(c,lambda:0.,lambda n:None)
            self.assertEqual(c.calls,1)
    def test_reversed_clock_rejected(self):
        values=iter([1.,.5])
        with self.assertRaisesRegex(ValueError,'clock'):poll_window(Client(),lambda:next(values),lambda n:None)
    def test_retention_decoder_keeps_known_wifi_reply(self):
        from component_receive_analysis_v3 import correlate
        from test_component_receive_analysis import reply,trace
        from test_analyse_short_ram_path import wifi_capture
        payload=reply();result=correlate(trace(payload),wifi_capture(payload,1000000000))
        self.assertTrue(result['complete_receive_coverage']);self.assertEqual(result['matched_receive_rows'],1)

if __name__=='__main__':unittest.main()
