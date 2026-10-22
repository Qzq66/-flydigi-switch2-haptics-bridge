"""Client protocol checks using fake datagrams and clock; opens no sockets."""
import json
import socket
import struct
import zlib
from unittest.mock import patch
from bridge_runtime import BridgeFault, Client, unpack, collect_frames
from bridge_input import NEUTRAL

checks = []
SESSION = 123
PEER = ('192.168.137.2', 49724)
NEUTRAL_MOTORS = bytes.fromhex('0001404000014040')


def check(name, ok):
    checks.append(dict(name=name, passed=bool(ok)))
    if not ok:
        raise AssertionError(name)


def faults(call):
    try:
        call()
    except BridgeFault:
        return True
    return False


def packet(request, flags=7, events=(), boot=4, nonce=SESSION, stamp=10000):
    body = struct.pack('<4sBBHQIIIHH', b'BHR2', 2, flags,
                       36 + 16 * len(events), nonce, request, boot, stamp, len(events), 0)
    for seq, at, motors in events:
        body += struct.pack('<II8s', at, seq, motors)
    return body + struct.pack('<I', zlib.crc32(body))


class FakeSocket:
    def __init__(self):
        self.replies = []
        self.sent = []
        self.closed = False

    def bind(self, address):
        self.bound = address

    def settimeout(self, timeout):
        self.timeout = timeout

    def sendto(self, data, peer):
        self.sent.append((data, peer))

    def recvfrom(self, size):
        if not self.replies:
            raise socket.timeout()
        item = self.replies.pop(0)
        if item is None:
            raise socket.timeout()
        if callable(item):
            return item(self)
        return item

    def close(self):
        self.closed = True


def current(sock, **kwargs):
    request = struct.unpack_from('<I', sock.sent[-1][0], 4)[0]
    return packet(request, **kwargs), PEER


def setup(input_source=None):
    sock = FakeSocket()
    with patch('bridge_runtime.socket.socket', return_value=sock), patch('bridge_runtime.secrets.randbits', return_value=0):
        client = Client(PEER[0], SESSION, input_source=input_source)
    return client, sock


# A constant clock removes machine-speed dependencies; a fake receive always
# either supplies a datagram or raises a timeout, so no loop can wait on I/O.
with patch('bridge_runtime.time.perf_counter', return_value=1.0):
    c, s = setup()
    check('unseen_end_cannot_send_BHE2', faults(lambda: c.confirm_end()) and not s.sent)

    c, s = setup()
    s.replies = [lambda sock: current(sock, flags=9, events=[(0, 9000, NEUTRAL_MOTORS)])]
    f = c.poll()
    check('last_neutral_event_retained_while_draining', len(f['events']) == 1 and c.received == 1 and c.ack == 0)
    check('draining_alone_is_not_complete', not c.terminal_received and faults(lambda: c.confirm_end()))
    s.replies = [lambda sock: current(sock, flags=9, events=[(0, 9000, NEUTRAL_MOTORS)])]
    check('duplicate_tail_not_rendered_twice', c.poll()['events'] == [] and c.duplicates == 1)
    s.replies = [lambda sock: current(sock, flags=25)]
    c.poll()
    check('empty_complete_marker_received', c.terminal_received and not c.terminal_ack_replied)
    s.replies = [None, None, lambda sock: current(sock, flags=25)]
    reply = c.confirm_end()
    queries = [struct.unpack('<4sIQI', data) for data, _ in s.sent if data[:4] == b'BHE2']
    check('end_confirmation_retries_timeouts_then_acknowledges', reply is not None and c.terminal_ack_replied and len(queries) == 3)
    check('end_confirmation_carries_last_event_ack', all(q[2:] == (SESSION, 0) for q in queries))
    c.close()
    check('fake_transport_closed', s.closed)

    c, s = setup()
    s.replies = [lambda sock: current(sock, flags=25)]
    c.poll()
    s.replies = [None, None, None]
    check('missing_end_reply_is_not_success_and_retries_bounded', c.confirm_end() is None and not c.terminal_ack_replied and len(s.sent) == 4)

    c, s = setup()
    s.replies = [lambda sock: current(sock, flags=25)]
    c.poll()
    s.replies = [lambda sock: current(sock, flags=9)]
    check('noncomplete_end_reply_rejected', faults(lambda: c.confirm_end()) and not c.terminal_ack_replied)

    c, s = setup()
    s.replies = [lambda sock: current(sock, flags=9)]
    c.poll()
    s.replies = [lambda sock: current(sock, flags=7)]
    check('upstream_cannot_resume_after_drain_marker', faults(lambda: c.poll()))

    c, s = setup()
    s.replies = [lambda sock: current(sock, flags=25)]
    c.poll()
    s.replies = [lambda sock: current(sock, flags=25, boot=5)]
    check('restart_during_confirmation_rejected', faults(lambda: c.confirm_end()))

    c, s = setup()
    s.replies = [lambda sock: current(sock, events=[(1, 9000, NEUTRAL_MOTORS)])]
    check('missing_tail_sequence_rejected', faults(lambda: c.poll()))

    c, s = setup()
    s.replies = [lambda sock: (packet(0), PEER), lambda sock: (packet(1), ('192.168.137.99', 49724)),
                 lambda sock: current(sock, events=[(0, 9000, NEUTRAL_MOTORS)])]
    check('old_request_and_foreign_peer_ignored', len(c.poll()['events']) == 1 and c.received == 1)

    c, s = setup(input_source=lambda: NEUTRAL)
    s.replies = [lambda sock: current(sock)]
    c.poll()
    data = s.sent[-1][0]
    check('input_relay_36byte_layout_and_sequence', len(data) == 36 and data[:4] == b'BHI2' and struct.unpack_from('<I', data, 20)[0] == 1 and data[24:33] == NEUTRAL)
    s.replies = [lambda sock: current(sock, flags=25)]
    c.poll()
    s.replies = [lambda sock: current(sock, flags=25)]
    c.confirm_end()
    check('final_ack_does_not_sample_input_source', len(s.sent[-1][0]) == 20 and s.sent[-1][0][:4] == b'BHE2')

    c, s = setup(input_source=lambda: NEUTRAL)
    s.replies = [lambda sock: current(sock, flags=9)]
    c.poll()
    def disconnected_input():
        raise BridgeFault('Input disconnected after upstream shutdown')
    c.input_source = disconnected_input
    s.replies = [lambda sock: current(sock, flags=25)]
    c.poll()
    check('drain_uses_BHP2_without_sampling_disconnected_input', s.sent[-1][0][:4] == b'BHP2' and len(s.sent[-1][0]) == 20 and c.terminal_received)

    c, s = setup(input_source=lambda: bytes(8))
    check('malformed_input_stops_before_send', faults(lambda: c.poll()) and not s.sent)

    c, s = setup()
    published = []
    def ack_after_stop(sock):
        check('collector_signals_stop_before_waiting_for_end_ack', [f['flags'] for f in published] == [9])
        return current(sock, flags=25)
    s.replies = [lambda sock: current(sock, flags=25), ack_after_stop]
    collect_frames(c, published.append, lambda: False, pause=lambda _: None)
    check('collector_only_publishes_complete_after_confirmation', [f['flags'] for f in published] == [9, 25] and c.terminal_ack_replied)

    c, s = setup()
    published = []
    s.replies = [lambda sock: current(sock, flags=25), None, None, None]
    check('collector_missing_ack_faults_without_complete_publication', faults(lambda: collect_frames(c, published.append, lambda: False, pause=lambda _: None)) and [f['flags'] for f in published] == [9])

    c, s = setup()
    published = []
    s.replies = [lambda sock: current(sock, flags=9, events=[(0, 9000, NEUTRAL_MOTORS)]),
                 lambda sock: current(sock, flags=25), lambda sock: current(sock, flags=25)]
    collect_frames(c, published.append, lambda: False, pause=lambda _: None)
    check('collector_preserves_tail_event_before_complete', [f['flags'] for f in published] == [9, 9, 25] and sum(len(f['events']) for f in published) == 1)

    c, s = setup()
    collect_frames(c, lambda _: None, lambda: True, pause=lambda _: None)
    check('stopped_collector_sends_no_network_query', not s.sent)

for flags, events in ((17, []), (31, []), (25, [(0, 9000, NEUTRAL_MOTORS)])):
    check('invalid_end_flags_or_payload_' + str(flags), faults(lambda: unpack(packet(1, flags, events), SESSION, 1)))

print(json.dumps(checks, indent=2))
