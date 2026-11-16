"""Bounded first-test Switch 0x10 USB reports; no device I/O.

Protocol values checked against pinned Bluepad32 Switch frequency/amplitude tables.
80 is a table amplitude (approximately 0.080), not a calibrated physical strength.
"""
NEUTRAL = bytes.fromhex('00014040')
LOW_160 = bytes.fromhex('801ac046')


def report(sequence, left=False, right=False):
    if type(sequence) is not int or not 0 <= sequence < 16:
        raise ValueError('Sequence must be a 4-bit integer')
    if type(left) is not bool or type(right) is not bool:
        raise ValueError('Only fixed low-strength or neutral channel states allowed')
    return bytes((0x10, sequence)) + (LOW_160 if left else NEUTRAL) + (
        LOW_160 if right else NEUTRAL) + bytes(54)


def validate(packet):
    packet = bytes(packet)
    if len(packet) != 64 or packet[0] != 0x10 or packet[1] > 15 or any(packet[10:]):
        raise ValueError('Not a reviewed USB rumble packet')
    if packet[2:6] not in (NEUTRAL, LOW_160) or packet[6:10] not in (NEUTRAL, LOW_160):
        raise ValueError('Unreviewed motor parameters')
    return packet
