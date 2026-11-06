"""Taking the keyboard over must not add a noticeable delay.

The remapper grabs the device, reads each event on its own thread and writes the
result to a virtual keyboard. That is one extra hop, and a hop that waited would be
felt on every key. These tests drive the real reader thread — the same _run, the same
select loop, the same _read_keys — and measure how long an event spends inside it.

The device is a pipe and the virtual keyboard is a sink that records a timestamp, so
nothing here needs /dev/uinput or a real keyboard.
"""

from __future__ import annotations

import inspect
import os
import struct
import threading
import time

import pytest

from logi_ghub import keyremap

EVENT = keyremap.EVENT
EV_KEY = 1


class Sink:
    """A virtual keyboard that records when it was asked to type."""

    def __init__(self):
        self.stamps: list[tuple[float, int, bool]] = []
        self.lock = threading.Lock()

    def key(self, code: int, down: bool):
        with self.lock:
            self.stamps.append((time.perf_counter(), code, down))

    def wheel(self, clicks, horizontal=False):
        pass

    def close(self):
        pass

    def count(self) -> int:
        with self.lock:
            return len(self.stamps)


def _event(code: int, value: int) -> bytes:
    return EVENT.pack(0, 0, EV_KEY, code, value)


def _remapper(fd: int, sink: Sink) -> keyremap.KeyRemapper:
    """A KeyRemapper wired to one already-open fd, without grabbing anything.

    __init__ and start() open real devices and grab them; the parts that matter here
    are the reader thread and its mapper, so only those are set up.
    """
    r = keyremap.KeyRemapper.__new__(keyremap.KeyRemapper)
    r.name = "test keyboard"
    r.nodes = [keyremap.EventNode("/dev/input/event0", "test", {30}, set())]
    r.mapping = {}
    r.gshift_mapping = {}
    r.on_layer = None
    r.pointer = None
    r.runner = None
    r.macros = {}
    r.tag = "keys"
    r.fds = {fd: r.nodes[0]}
    r.virtual = sink
    r.lost = False
    r.panicked = False
    r._wake_r, r._wake_w = os.pipe()
    r._stopping = threading.Event()
    r._close_lock = threading.Lock()
    r.mapper = keyremap.KeyMapper({}, sink, None, None, {})
    r.thread = threading.Thread(target=r._run, name="test-keys", daemon=True)
    r.thread.start()
    return r


@pytest.fixture
def pipe_and_thread():
    read_fd, write_fd = os.pipe()
    os.set_blocking(read_fd, False)
    sink = Sink()
    r = _remapper(read_fd, sink)
    try:
        yield write_fd, sink, r
    finally:
        r._stopping.set()
        try:
            os.write(r._wake_w, b"x")
        except OSError:
            pass
        r.thread.join(timeout=2)
        for fd in (read_fd, write_fd, r._wake_r, r._wake_w):
            try:
                os.close(fd)
            except OSError:
                pass


def _round_trip(write_fd: int, sink: Sink, count: int) -> list[float]:
    """Send `count` presses and return how long each took to come out the other side."""
    sent: list[float] = []
    for _ in range(count):
        sent.append(time.perf_counter())
        os.write(write_fd, _event(30, 1) + _event(30, 0))
        # The reader is one thread and the pipe is bounded; letting it drain keeps
        # the measurement about the code, not about the buffer.
        deadline = time.perf_counter() + 2.0
        while sink.count() < 2 * (len(sent)) and time.perf_counter() < deadline:
            time.sleep(0)
    deadline = time.perf_counter() + 2.0
    while sink.count() < 2 * count and time.perf_counter() < deadline:
        time.sleep(0.001)
    assert sink.count() == 2 * count, f"only {sink.count()} of {2 * count} events came out"
    with sink.lock:
        presses = [s for s in sink.stamps if s[2] is True]
    return [presses[i][0] - sent[i] for i in range(count)]


def test_a_key_comes_out_in_well_under_a_frame(pipe_and_thread):
    """Under 16 ms means the hop cannot be told apart from the keyboard itself."""
    write_fd, sink, _r = pipe_and_thread
    latencies = _round_trip(write_fd, sink, 50)
    worst = max(latencies)
    assert worst < 0.016, f"worst-case delay was {worst * 1000:.1f} ms"


def test_the_average_is_a_fraction_of_a_millisecond(pipe_and_thread):
    write_fd, sink, _r = pipe_and_thread
    latencies = _round_trip(write_fd, sink, 100)
    mean = sum(latencies) / len(latencies)
    assert mean < 0.002, f"average delay was {mean * 1000:.2f} ms"


def test_the_delay_does_not_grow_with_the_backlog(pipe_and_thread):
    """A fixed cost per event; anything that queued up would show as a rising tail."""
    write_fd, sink, _r = pipe_and_thread
    latencies = _round_trip(write_fd, sink, 200)
    first_ten = sum(latencies[:10]) / 10
    last_ten = sum(latencies[-10:]) / 10
    assert last_ten < max(first_ten * 5, 0.004), (
        f"the tail got slower: {first_ten * 1000:.2f} ms → {last_ten * 1000:.2f} ms")


def test_the_reader_never_sleeps():
    """Sleeping on the read path would add exactly the delay this guards against."""
    for fn in (keyremap.KeyRemapper._read_keys, keyremap.KeyMapper.handle):
        src = inspect.getsource(fn)
        assert "sleep" not in src, f"{fn.__name__} sleeps on the key path"


def test_the_reader_waits_on_select_not_on_a_poll_interval():
    """select() wakes on the event itself; a poll loop would round every key up to its tick."""
    src = inspect.getsource(keyremap.KeyRemapper._run)
    assert "select.select" in src
    assert "timeout" not in src.replace("timeout=2", ""), "the loop polls with a timeout"


def test_one_write_of_many_events_is_read_in_one_go(pipe_and_thread):
    """A burst is read as a burst, not one syscall per event."""
    write_fd, sink, _r = pipe_and_thread
    burst = b"".join(_event(30, 1) + _event(30, 0) for _ in range(32))
    start = time.perf_counter()
    os.write(write_fd, burst)
    deadline = start + 2.0
    while sink.count() < 64 and time.perf_counter() < deadline:
        time.sleep(0)
    assert sink.count() == 64
    assert time.perf_counter() - start < 0.016
