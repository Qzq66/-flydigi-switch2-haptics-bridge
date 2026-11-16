"""Offline, privacy-preserving analysis of BTD1 discovery captures. No device I/O."""
import argparse
import json
from pathlib import Path
import re


def decode_hex(value, limit):
    if value == '-':
        return b''
    if not re.fullmatch(r'(?:[0-9a-fA-F]{2})*', value) or len(value) > limit * 2:
        raise ValueError('invalid hex field')
    return bytes.fromhex(value)


def analyse(raw):
    errors, warnings, peers = [], [], {}
    phases, ready, done = [], False, None
    observations = {'CLASSIC': 0, 'BLE': 0}
    if len(raw) > 65536:
        raise ValueError('capture exceeds 64 KiB')
    for line in raw.decode('ascii', errors='strict').splitlines():
        if not line.startswith('BTD1 '):
            continue
        parts = line.split()
        kind = parts[1]
        try:
            if done is not None:
                raise ValueError('record after DONE')
            if kind == 'READY':
                if ready or phases:
                    raise ValueError('duplicate or late READY')
                fields = dict(p.split('=', 1) for p in parts[2:])
                if fields.get('no_pair') != '1' or fields.get('storage') != 'ram':
                    raise ValueError('unexpected probe safety metadata')
                ready = True
            elif kind == 'PHASE':
                if not ready or parts[2:] != [['CLASSIC'], ['BLE']][len(phases)]:
                    raise ValueError('invalid phase order')
                phases.append(parts[2])
            elif kind in observations:
                if not phases or phases[-1] != kind:
                    raise ValueError('observation outside phase')
                fields = dict(p.split('=', 1) for p in parts[2:])
                addr = decode_hex(fields['addr'], 6)
                if len(addr) != 6:
                    raise ValueError('invalid address length')
                observations[kind] += 1
                address_type = int(fields['type']) if kind == 'BLE' else None
                if address_type is not None and address_type not in (0, 1, 2, 3):
                    raise ValueError('invalid address type')
                key = (kind, addr, address_type)
                peer = peers.setdefault(key, {'peer_id': 'peer_%02d' % (len(peers) + 1),
                    'transport': kind, 'name_present': False, 'hid_hint': False,
                    'advertised_service_uuids': []})
                if kind == 'CLASSIC':
                    peer['name_present'] |= bool(decode_hex(fields['name'], 64))
                    if not re.fullmatch('[0-9a-fA-F]{6}', fields['cod']):
                        raise ValueError('invalid class of device')
                    peer['peripheral_class_hint'] = ((int(fields['cod'], 16) >> 8) & 31) == 5
                else:
                    data = decode_hex(fields['data'], 31)
                    offset = 0
                    while offset < len(data):
                        size = data[offset]
                        if size == 0:
                            break
                        end = offset + 1 + size
                        if end > len(data):
                            raise ValueError('truncated advertising field')
                        ad_type, payload = data[offset + 1], data[offset + 2:end]
                        if ad_type in (8, 9):
                            peer['name_present'] |= bool(payload)
                        width = {2: 2, 3: 2, 6: 16, 7: 16}.get(ad_type)
                        if width:
                            if len(payload) % width:
                                raise ValueError('misaligned service UUID list')
                            for i in range(0, len(payload), width):
                                uuid = payload[i:i + width][::-1].hex()
                                if uuid not in peer['advertised_service_uuids']:
                                    peer['advertised_service_uuids'].append(uuid)
                                peer['hid_hint'] |= uuid == '1812'
                        offset = end
            elif kind == 'DONE':
                done = dict(p.split('=', 1) for p in parts[2:])
                for field in ('classic', 'ble', 'dropped', 'ram_errors', 'ram_writes', 'ram_erases'):
                    if not done[field].isdigit():
                        raise ValueError('invalid counter')
                if int(done['ram_errors']):
                    errors.append('RAM storage error')
                if any(int(done[k.lower()]) != observations[k] for k in observations):
                    errors.append('observation count mismatch')
                if int(done['dropped']):
                    warnings.append('observation capacity reached; scan is not exhaustive')
            else:
                raise ValueError('unknown record type')
        except (ValueError, KeyError, IndexError):
            errors.append('invalid discovery record')
    complete = ready and phases == ['CLASSIC', 'BLE'] and done is not None and done.get('reason') == 'complete'
    if not complete:
        warnings.append('capture incomplete; absence is not evidence of unsupported Bluetooth')
    if not peers:
        warnings.append('no observations; device mode or discovery timing remains unverified')
    return {'schema': 'bt-discovery-v1', 'status': 'FAILED' if errors else 'COMPLETE' if complete else 'INCOMPLETE',
        'errors': errors, 'warnings': warnings, 'peers': list(peers.values()),
        'observations': observations, 'physical_device_count': None,
        'identity_verified': False, 'full_services_enumerated': False,
        'input': 'UNVERIFIED', 'haptics': 'UNVERIFIED',
        'scope': 'discovery only; names and advertised UUIDs do not prove identity or capabilities'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.capture.resolve() == args.report.resolve():
        parser.error('report must not overwrite capture')
    with args.capture.open('rb') as stream:
        result = analyse(stream.read(65537))
    with args.report.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False)
    print('%s: %d transport/address observations; input/haptics UNVERIFIED' %
          (result['status'], len(result['peers'])))
    return 1 if result['status'] != 'COMPLETE' else 0


if __name__ == '__main__':
    raise SystemExit(main())
