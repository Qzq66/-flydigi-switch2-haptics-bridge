import pathlib,json,struct,datetime,collections
root=pathlib.Path(__file__).absolute().parent.parent
log=json.loads((root/'outputs/pico-persistent-capture-20261022-134847.json').read_text(encoding='utf-8-sig'))['newest']
d=bytes.fromhex(log['diagnostics_raw_hex'])
counts=dict(zip(('received','replies','rumble_fields','rejected','overflow','short_packets'),struct.unpack_from('<6I',d,8)))
counts.update(dict(zip(('input_frames','LR_pressed_frames','released_frames'),struct.unpack_from('<3I',d,48))))
hist=collections.Counter(e['subcommand'] for e in log['events'] if e['subcommand'])
retained_ack_requests=sum(e['report_id']=='01' or (e['report_id']=='80' and e['raw_hex']=='8002') for e in log['events'])
report=dict(recorded_at=datetime.datetime.now().astimezone().isoformat(),firmware='0.3.4',
    source='pico-persistent-capture-20261022-134847.json',crc_valid=log['crc_valid'],
    duration_ms=log['elapsed_ms'],counts=counts,usb_stage=d[40],player_lights=d[41],
    imu_mode=d[42],vibration_enabled=d[43],registration_flags=d[60],
    mounts=d[61],unmounts=d[62],suspends=d[63],retained_command_histogram=dict(hist),
    retained_requests_requiring_reply=retained_ack_requests,
    reply_count_excluding_initial_unsolicited_identify=counts['replies']-1,
    omitted_events=log['dropped_middle_events'],
    user_observation='Controller icon appeared and disappeared at the planned 20 second cutoff',
    conclusions=['No rejected commands observed in whole-run counters',
        'Host advanced past 0x21 and set player-light value 01 at 3862 ms',
        'LR press and release were sent; no USB unmount or suspend before capture deadline',
        'Continuous haptics fidelity and Flydigi forwarding remain untested'])
(root/'outputs/switch2-v034-analysis.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
