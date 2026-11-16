"""Plan-level tests for the haptic probe (no device, no threads)."""
import unittest

import switch_usb_haptic_probe as h
from switch_rumble_packet import NEUTRAL, LOW_160, validate


class Tests(unittest.TestCase):
    def test_plan_has_three_segments_then_neutral_tail(self):
        frames = h.plan()
        self.assertEqual(len(frames), 3 * h.SEGMENT_FRAMES + h.TAIL_FRAMES)
        self.assertEqual([f[0] for f in frames[:h.SEGMENT_FRAMES]], ['left'] * h.SEGMENT_FRAMES)
        self.assertEqual([f[0] for f in frames[-h.TAIL_FRAMES:]], ['neutral'] * h.TAIL_FRAMES)

    def test_every_planned_packet_is_a_reviewed_packet(self):
        for _, packet in h.plan():
            validate(packet)

    def test_segment_channels_are_what_the_label_says(self):
        frames = h.plan()
        left = frames[0][1]
        right = frames[h.SEGMENT_FRAMES][1]
        both = frames[2 * h.SEGMENT_FRAMES][1]
        self.assertEqual(left[2:6], LOW_160)
        self.assertEqual(left[6:10], NEUTRAL)
        self.assertEqual(right[2:6], NEUTRAL)
        self.assertEqual(right[6:10], LOW_160)
        self.assertEqual(both[2:6], LOW_160)
        self.assertEqual(both[6:10], LOW_160)


if __name__ == '__main__':
    unittest.main()
