"""Overlap the 8 ms blocking WriteFile with the dispatcher.

The Switch-mode OUT endpoint polls once per 8 ms (measured 2026-11-16: back-to-back
writes complete every 8.00 ms). A synchronous writer therefore occupies exactly one
full dispatch period, leaving no margin. This writer keeps a single "latest frame"
slot and hands it to a worker thread, so the dispatcher only pays the submit cost.

Safety: submission never blocks and never queues more than one frame; if the worker
is busy, the older pending frame is replaced and counted as replaced. No motor
parameters, no configuration, no initialization: frames are whatever the caller
submits.
"""
import threading
import time


class AsyncWriter:
    def __init__(self, writer, clock=time.perf_counter, timeout_ms=50):
        self._writer = writer
        self._timeout_ms = timeout_ms
        self._clock = clock
        self._lock = threading.Lock()
        self._ready = threading.Event()
        self._closed = False
        self._slot = None
        self._busy = False
        self.submitted = 0
        self.replaced = 0
        self.written = 0
        self.failed = 0
        self.max_write_ms = 0.0
        self.max_backlog_ms = 0.0
        self.error = None
        self._thread = threading.Thread(target=self._run, name='switch-async-writer', daemon=True)
        self._thread.start()

    def submit(self, packet):
        stamp = self._clock()
        with self._lock:
            if self._closed:
                raise RuntimeError('writer closed')
            if self._slot is not None:
                self.replaced += 1
            self._slot = (packet, stamp)
            self.submitted += 1
        self._ready.set()

    def _run(self):
        while True:
            self._ready.wait()
            with self._lock:
                if self._closed and self._slot is None:
                    self._ready.clear()
                    return
                item = self._slot
                self._slot = None
                if item is None:
                    self._ready.clear()
                    continue
                self._busy = True
            packet, stamp = item
            started = self._clock()
            backlog = (started - stamp) * 1000
            if backlog > self.max_backlog_ms:
                self.max_backlog_ms = backlog
            try:
                self._writer.send(packet, timeout_ms=self._timeout_ms)
                with self._lock:
                    self.written += 1
                elapsed = (self._clock() - started) * 1000
                if elapsed > self.max_write_ms:
                    self.max_write_ms = elapsed
            except Exception as exc:  # keep the diagnostic alive; report at the end
                with self._lock:
                    self.failed += 1
                    self.error = str(exc)
            finally:
                with self._lock:
                    self._busy = False
                    if self._slot is None:
                        self._ready.clear()

    def wait_idle(self, timeout=2.0):
        until = time.monotonic() + timeout
        while time.monotonic() < until:
            with self._lock:
                if not self._busy and self._slot is None:
                    return True
            time.sleep(.001)
        return False

    def close(self, timeout=2.0):
        with self._lock:
            self._closed = True
        self._ready.set()
        self._thread.join(timeout)
        self._writer.close()

    def summary(self):
        return {
            'submitted': self.submitted,
            'written': self.written,
            'replaced': self.replaced,
            'failed': self.failed,
            'max_write_ms': round(self.max_write_ms, 4),
            'max_backlog_ms': round(self.max_backlog_ms, 4),
            'error': self.error,
        }
