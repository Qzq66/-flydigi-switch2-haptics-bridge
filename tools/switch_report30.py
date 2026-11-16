"""Decode observed standard Switch 0x30 input fields. Pure offline, no device I/O."""


def axes(data):
    return data[0] | ((data[1] & 15) << 8), (data[1] >> 4) | (data[2] << 4)


def decode(packet):
    packet = bytes(packet)
    if not 49 <= len(packet) <= 64 or packet[0] != 0x30:
        raise ValueError('Expected standard Switch report 0x30, 49..64 bytes')
    lx, ly = axes(packet[6:9])
    rx, ry = axes(packet[9:12])
    return dict(a=bool(packet[3] & 8), b=bool(packet[3] & 4),
                x=bool(packet[3] & 2), y=bool(packet[3] & 1),
                right_buttons=packet[3], misc_buttons=packet[4], left_buttons=packet[5],
                misc_active_buttons=packet[4] & 0x3f, misc_status_bits=packet[4] & 0xc0,
                lx=lx, ly=ly, rx=rx, ry=ry)


def require_neutral(samples):
    if not samples:
        raise ValueError('NO_INPUT_BASELINE')
    for item in samples:
        # Standard Pro +/-/stick/Home/Capture are bits0..5. Keep raw upper bits visible.
        if item['right_buttons'] or item['misc_active_buttons'] or item['left_buttons']:
            raise ValueError('BUTTONS_NOT_RELEASED')
        if item['misc_status_bits'] not in (0, 0x80):
            raise ValueError('UNREVIEWED_MISC_STATUS_BITS')
        if any(abs(item[x]-2048) > 512 for x in ('lx', 'ly', 'rx', 'ry')):
            raise ValueError('STICKS_NOT_CENTERED')
