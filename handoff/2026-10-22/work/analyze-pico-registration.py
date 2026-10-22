"""Offline registration trace summary; never opens any device."""
import pathlib,json,struct,datetime,collections
root=pathlib.Path(__file__).absolute().parent.parent
source=root/'outputs/pico-persistent-capture-20261022-133525.json'
log=json.loads(source.read_text(encoding='utf-8-sig'))['newest']
d=bytes.fromhex(log['diagnostics_raw_hex'])
counts=dict(zip(('received','replies','rumble_fields_received','rejected','overflow','short_packets'),struct.unpack_from('<6I',d,8)))
counts.update(dict(zip(('input_reports_sent','pressed_reports_sent','released_reports_sent'),struct.unpack_from('<3I',d,48))))
rumble=[]
for event in log['events']:
    raw=bytes.fromhex(event['raw_hex'])
    if raw[0]==0x10 and len(raw)>=10:
        rumble.append({'at_ms':event['at_ms'],'packet_counter':raw[1],
            'left_hex':raw[2:6].hex(),'right_hex':raw[6:10].hex(),
            'raw_hex':event['raw_hex']})
report=dict(recorded_at=datetime.datetime.now().astimezone().isoformat(),source=source.name,
    user_observation='New controller icon appeared; disappeared at about 20 seconds',
    crc_valid=log['crc_valid'],elapsed_ms=log['elapsed_ms'],total_events=log['total_events'],
    retained_events=len(log['events']),dropped_middle_events=log['dropped_middle_events'],
    counts=counts,input_mode=d[5],usb_stage=d[40],player_lights=d[41],imu_mode=d[42],vibration_enabled=d[43],
    registration_flags=d[60],mount_count=d[61],unmount_count=d[62],suspend_count=d[63],
    retained_command_histogram=dict(collections.Counter(e['subcommand'] for e in log['events'] if e['subcommand'])),
    rumble_events=rumble,
    conclusions=['USB controller icon and L+R response observed by user',
        'Host enabled vibration at 3771ms, then sent changing 0x10 output payloads',
        'Exactly one bounded press interval in firmware; counters show press and release reports sent',
        'Unsupported 0x21 repeated after registration; compatibility incomplete',
        'No Flydigi output, waveform decode or end-to-end haptics validated in this test',
        'Player number not confirmed: last player-light value remained zero',
        'Trace retains first/last 24 events, not a complete haptics stream'])
out=root/'outputs/switch2-registration-analysis.json'
out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
(root/'outputs/switch2-rumble-retained-samples.json').write_text(json.dumps(rumble,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k not in ('rumble_events','conclusions')},ensure_ascii=False,indent=2))
