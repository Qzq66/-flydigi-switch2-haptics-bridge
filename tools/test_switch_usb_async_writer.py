"""Tests for the overlapped writer (no device, no threads blocked on hardware)."""
import threading
import time
import unittest

import switch_usb_async_writer as a


class FakeWriter:
    def __init__(self, delay=0.008):
        self.delay = delay
        self.sent = []
        self.closed = False
        self.lock = threading.Lock()

    def send(self, packet, timeout_ms=None):
        time.sleep(self.delay)
        with self.lock:
            self.sent.append(packet)

    def close(self):
        self.closed = True


class FailingWriter(FakeWriter):
    def send(self, packet, timeout_ms=None):
        raise RuntimeError('write failed')


class Tests(unittest.TestCase):
    def test_submit_does_not_wait_for_the_write(self):
        inner = FakeWriter(0.05)
        writer = a.AsyncWriter(inner)
        started = time.perf_counter()
        writer.submit(b'one')
        submit_ms = (time.perf_counter() - started) * 1000
        self.assertLess(submit_ms, 20)
        self.assertTrue(writer.wait_idle(1.0))
        writer.close()
        self.assertEqual(inner.sent, [b'one'])
        self.assertEqual(writer.written, 1)

    def test_pending_frame_is_replaced_not_queued(self):
        inner = FakeWriter(0.05)
        writer = a.AsyncWriter(inner)
        writer.submit(b'first')
        time.sleep(0.005)
        writer.submit(b'second')
        writer.submit(b'third')
        self.assertTrue(writer.wait_idle(2.0))
        writer.close()
        self.assertEqual(inner.sent[-1], b'third')
        self.assertLessEqual(len(inner.sent), 2)
        self.assertGreaterEqual(writer.replaced, 1)

    def test_failure_is_counted_and_does_not_kill_the_thread(self):
        writer = a.AsyncWriter(FailingWriter())
        writer.submit(b'x')
        self.assertTrue(writer.wait_idle(1.0))
        writer.close()
        self.assertEqual(writer.failed, 1)
        self.assertIn('write failed', writer.error)

    def test_close_flushes_and_closes_the_inner_writer(self):
        inner = FakeWriter(0.001)
        writer = a.AsyncWriter(inner)
        writer.submit(b'last')
        writer.close()
        self.assertTrue(inner.closed)
        self.assertEqual(inner.sent, [b'last'])

    def test_submit_after_close_is_rejected(self):
        writer = a.AsyncWriter(FakeWriter(0.001))
        writer.close()
        with self.assertRaises(RuntimeError):
            writer.submit(b'x')

    def test_transport_timeout_is_forwarded(self):
        class Recorder(FakeWriter):
            def __init__(self):
                FakeWriter.__init__(self, 0.0)
                self.timeouts = []

            def send(self, packet, timeout_ms=None):
                self.timeouts.append(timeout_ms)
                FakeWriter.send(self, packet, timeout_ms)

        inner = Recorder()
        writer = a.AsyncWriter(inner)
        writer.submit(b'x')
        writer.close()
        self.assertEqual(inner.timeouts, [50])


if __name__ == '__main__':
    unittest.main()
