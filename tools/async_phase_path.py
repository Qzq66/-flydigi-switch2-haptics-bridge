"""Candidate fix for the loop-body budget: publish the phase file off the dispatch thread.

The frozen loop writes `phase.json` synchronously every 200 ms.  Under the trial the
dispatched frames were never late (max 3.34 ms, 0/3181 over 4 ms) yet the gate still fired,
so the remaining suspect is the loop body itself; a slow write lands between two ticks.

`AsyncPhasePath` keeps the same duck-typed path interface the frozen loop calls, but enqueues
each payload to one daemon writer.  The loop never waits on the disk; the order of writes is
preserved; a persistent failure is recorded and reported instead of killing the loop.  Call
`close()` before the process exits so the final `ENDED` state is flushed.

Enable with FLYDIGI_ASYNC_PHASE=1; disabled, callers keep the synchronous path.
"""
import os
import pathlib
import queue
import threading
import time


def enabled():
    return os.environ.get('FLYDIGI_ASYNC_PHASE') == '1'


class AsyncPhasePath(object):
    def __init__(self, inner, max_pending=256):
        self._inner = pathlib.Path(inner)
        self._queue = queue.Queue(maxsize=max_pending)
        self._pending = 0
        self._lock = threading.Lock()
        self._errors = []
        self._written = 0
        self._closed = False
        self._thread = threading.Thread(target=self._run, name='phase-writer', daemon=True)
        self._thread.start()

    def write_text(self, data, **kwargs):
        if self._closed:
            return self._inner.write_text(data, **kwargs)
        try:
            self._queue.put_nowait(data)
        except queue.Full:
            # Never block the dispatch thread: fall back to one synchronous write.
            with self._lock:
                self._pending += 1
            try:
                return self._inner.write_text(data, **kwargs)
            finally:
                with self._lock:
                    self._pending -= 1
        return len(data)

    def _run(self):
        while True:
            item = self._queue.get()
            if item is None:
                return
            with self._lock:
                self._pending += 1
            try:
                self._write(item)
            except BaseException as exc:  # recorded, never raised into the loop
                self._errors.append(repr(exc))
            finally:
                with self._lock:
                    self._pending -= 1

    def _write(self, data):
        last = None
        for _ in range(8):
            try:
                self._inner.write_text(data)
                self._written += 1
                return
            except PermissionError as exc:  # Windows sharing violation with the Tk reader
                last = exc
                time.sleep(.002)
        raise last

    def flush(self, timeout=2.0):
        deadline = time.perf_counter() + timeout
        while time.perf_counter() < deadline:
            with self._lock:
                pending = self._pending
            if pending == 0 and self._queue.empty():
                return True
            time.sleep(.002)
        return False

    def close(self, timeout=2.0):
        if not self._closed:
            self._closed = True
            self._queue.put(None)
            self._thread.join(timeout)
        return self.stats()

    def stats(self):
        return dict(written=self._written, pending=self._pending, closed=self._closed,
                    errors=list(self._errors[-8:]), error_count=len(self._errors))

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def __fspath__(self):
        return str(self._inner)

    def __str__(self):
        return str(self._inner)
