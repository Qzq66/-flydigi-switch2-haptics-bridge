"""Offline: does the 2 ms spin cost the collector any packets? (no device)

`spin_wait_probe.py` shows sleep-until-2 ms + spin puts every dispatch inside the 4 ms gate.
The open question is the receiver: the spin holds the GIL and the CPU, and the collector runs
in the same process.  This probe measures that cost on a loopback socket instead of assuming
it away:

    sender   normal thread, 125 packets/s, 8 ms apart, 64-byte payload with a sequence number
    receiver normal thread, blocking recvfrom with a 1 ms timeout, records arrival time + seq
    main     the same 8 ms deadline loop in two arms:
               baseline  1 ms sleep, dispatch when now >= target
               spin_2ms  sleep until target - 2 ms, spin the last 2 ms

Reported per arm: loop dispatch lateness (the gate quantity), packets sent/received, lost
sequences, and the receive-gap tail (max / p99 / count over 8 ms).  Loopback removes radio
loss, so any lost or delayed packet here is caused by host scheduling - which is the point.
"""
import argparse, json, pathlib, socket, threading, time

from priority_coverage_probe import GATE, PERIOD, stats
from spin_wait_probe import margin_for

ROOT = pathlib.Path(__file__).resolve().parent.parent
CAMPAIGN = ROOT / 'docs/campaigns/outer-loop-2026-11-15'
PACKET_INTERVAL = 0.008
WAIT = 0.001
ARMS = ('baseline', 'spin_2ms')


def validate_arm(arm):
    if arm not in ARMS:
        raise ValueError('Unknown arm: %s' % arm)
    return arm


def summarize_receive(sequences, arrivals, sent):
    gaps = [b - a for a, b in zip(arrivals, arrivals[1:])]
    return dict(sent=sent, received=len(arrivals),
                lost=sent - len(arrivals),
                sequence_gaps=sum(1 for a, b in zip(sequences, sequences[1:]) if b != a + 1),
                gap_seconds=stats(gaps),
                gaps_over_8ms=sum(g > PERIOD for g in gaps),
                gaps_over_16ms=sum(g > 2 * PERIOD for g in gaps))


class Receiver(threading.Thread):
    def __init__(self, sock, stop):
        super().__init__(daemon=True)
        self.sock = sock
        self.stop = stop
        self.sequences = []
        self.arrivals = []
        self.error = None

    def run(self):
        try:
            while not self.stop.is_set():
                self.sock.settimeout(0.001)
                try:
                    data, _ = self.sock.recvfrom(256)
                except socket.timeout:
                    continue
                if len(data) >= 4:
                    self.sequences.append(int.from_bytes(data[:4], 'little'))
                    self.arrivals.append(time.perf_counter())
        except BaseException as exc:  # noqa: BLE001 - reported, not swallowed
            self.error = '%s: %s' % (type(exc).__name__, exc)


class Sender(threading.Thread):
    def __init__(self, sock, address, stop, count):
        super().__init__(daemon=True)
        self.sock = sock
        self.address = address
        self.stop = stop
        self.count = count
        self.sent = 0
        self.error = None

    def run(self):
        try:
            deadline = time.perf_counter()
            while not self.stop.is_set() and self.sent < self.count:
                self.sock.sendto(self.sent.to_bytes(4, 'little') + b'\0' * 60, self.address)
                self.sent += 1
                deadline += PACKET_INTERVAL
                delay = deadline - time.perf_counter()
                if delay > 0:
                    time.sleep(delay)
        except BaseException as exc:  # noqa: BLE001
            self.error = '%s: %s' % (type(exc).__name__, exc)


def run_arm(arm, periods):
    validate_arm(arm)
    margin = margin_for(arm)
    receiver_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    receiver_sock.bind(('127.0.0.1', 0))
    receiver_sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1 << 20)
    sender_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    stop = threading.Event()
    receiver = Receiver(receiver_sock, stop)
    sender = Sender(sender_sock, receiver_sock.getsockname(), stop, periods)
    receiver.start()
    sender.start()

    latencies = []
    started = time.perf_counter()
    target = started + PERIOD
    while len(latencies) < periods:
        now = time.perf_counter()
        if margin is None:
            if now < target:
                time.sleep(WAIT)
        else:
            spin_start = target - margin
            if now < spin_start:
                time.sleep(min(WAIT, spin_start - now))
            else:
                while time.perf_counter() < target:
                    pass
        now = time.perf_counter()
        if now >= target:
            latencies.append(now - target)
            target += PERIOD

    stop.set()
    sender.join(timeout=2)
    time.sleep(0.05)
    receiver.join(timeout=2)
    receiver_sock.close()
    sender_sock.close()
    return dict(
        dispatch=dict(lateness_seconds=stats(latencies), dispatched=len(latencies),
                      at_or_over_4ms=sum(v >= GATE for v in latencies)),
        receive=summarize_receive(receiver.sequences, receiver.arrivals, sender.sent),
        sender_error=sender.error, receiver_error=receiver.error)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--periods', type=int, default=2500)
    parser.add_argument('--arms', default=','.join(ARMS))
    parser.add_argument('--out', default=None)
    args = parser.parse_args()
    arms = [a.strip() for a in args.arms.split(',') if a.strip()]
    report = {arm: run_arm(arm, args.periods) for arm in arms}
    document = dict(status='PASSED_OFFLINE_RECV_SPIN', hardware_actions=0,
                    constants=dict(period_seconds=PERIOD, gate_seconds=GATE,
                                   packet_interval_seconds=PACKET_INTERVAL),
                    sample=dict(periods=args.periods), arms=report)
    text = json.dumps(document, indent=2, sort_keys=True) + '\n'
    if args.out:
        path = pathlib.Path(args.out)
        if not path.is_absolute():
            path = ROOT / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        print('WROTE', path)
    for arm in arms:
        d = report[arm]
        r = d['receive']
        print('%-9s lateness max %7.3f ms >=4ms %2d | sent %d recv %d lost %d | gap max %6.3f ms p99 %6.3f over8ms %d'
              % (arm, d['dispatch']['lateness_seconds'].get('maximum', 0) * 1e3,
                 d['dispatch']['at_or_over_4ms'], r['sent'], r['received'], r['lost'],
                 r['gap_seconds'].get('maximum', 0) * 1e3, r['gap_seconds'].get('p99', 0) * 1e3,
                 r['gaps_over_8ms']))


if __name__ == '__main__':
    main()
