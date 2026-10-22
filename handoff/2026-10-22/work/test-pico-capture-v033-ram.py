"""PC-side initialization/calibration tests for the exact neutral RAM candidate.

Never selects a real Pro controller by VID/PID alone; unique strings and the
read-only BPRO diagnostic magic must both match before any stateful command.
"""
import ctypes as C
import datetime
import importlib.util
import json
import pathlib
import random
import struct
import sys
import time

HERE=pathlib.Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('ro',HERE/'flydigi-readonly.py')
ro=importlib.util.module_from_spec(sp);sp.loader.exec_module(ro)
lib=ro.lib
handle=None
verified=False
allow_lr=False
report=dict(started_at=datetime.datetime.now().astimezone().isoformat(),checks=[],
            persistent_writes=0,physical_output=False,switch2_tested=False,
            intended_identity='057E:2009 / BPCAP-RP2350-LOCAL-033')

def check(name,ok):
    report['checks'].append(dict(name=name,passed=bool(ok)))
    if not ok:raise AssertionError(name)

def send(rid,payload=b'',read_probe=False):
    if rid not in (1,0x10,0x80) or len(payload)>63:raise ValueError('Unapproved candidate packet')
    if not verified and not read_probe:raise ValueError('Identity probe must pass first')
    data=(bytes([rid])+payload).ljust(64,b'\0')
    buf=C.create_string_buffer(data,64)
    if lib.hid_write(handle,buf,64)!=64:raise OSError('Candidate HID write failed')

def receive(rid,predicate=lambda _:True,timeout=1.5):
    until=time.perf_counter()+timeout
    while time.perf_counter()<until:
        buf=C.create_string_buffer(64)
        n=lib.hid_read_timeout(handle,buf,64,50)
        if n<0:raise OSError('Candidate HID read failed')
        if not n:continue
        packet=buf.raw[:n]
        if len(packet)!=64:raise AssertionError('Unexpected input report length')
        if packet[0] in (0x21,0x30):
            if packet[3:6] not in ((b'\0'*3,bytes.fromhex('400040')) if allow_lr else (b'\0'*3,)) or packet[6:12]!=bytes.fromhex('000880000880'):
                raise AssertionError('Non-neutral protocol state')
        if packet[0]==rid and predicate(packet):return packet
    raise TimeoutError(f'No matching report {rid:02X}')

def sub(cmd,args=b'',read_probe=False):
    send(1,b'\0'+bytes.fromhex('0001404000014040')+bytes([cmd])+args,read_probe=read_probe)
    return receive(0x21,lambda data:data[14]==cmd)

def read_virtual(address,size):
    if not 0<=size<=29:raise ValueError('Read size cap')
    args=struct.pack('<IB',address,size)
    packet=sub(0x10,args,read_probe=not verified)
    if packet[13]!=0x90 or packet[15:20]!=args:
        raise AssertionError(f'Virtual read header expected={args.hex()} actual={packet[13:20].hex()}')
    return packet[20:20+size]

def read_range(address,size):
    data=b''
    while len(data)<size:data+=read_virtual(address+len(data),min(29,size-len(data)))
    return data

def stats():
    p=read_range(0x9000,48)
    if p[:4]!=b'BCAP':raise ValueError('Not candidate firmware')
    return dict(version=p[4],mode=p[5],rumble_live=bool(p[6]),no_flash=p[7],
                **dict(zip(('received','replies','rumble_count','rejected','overflow','short_packets'),struct.unpack_from('<6I',p,8))),
                last_rumble=p[32:40].hex(),usb_stage=p[40],lights=p[41],imu=p[42],vibration=p[43],trace_count=struct.unpack_from('<I',p,44)[0])

def xy(data):
    raw=int.from_bytes(data,'little');return raw&4095,(raw>>12)&4095

def find_device():
    until=time.perf_counter()+20
    while time.perf_counter()<until:
        head=lib.hid_enumerate(0x057e,0x2009);matches=[]
        try:
            node=head
            while node:
                d=node.contents
                if d.product_string=='Bridge Pro Capture 033' and d.serial_number=='BPCAP-RP2350-LOCAL-033' and d.usage_page==1 and d.usage==4:
                    matches.append(bytes(d.path))
                node=d.next
        finally:
            if head:lib.hid_free_enumeration(head)
        if matches:return matches
        time.sleep(0.2)
    return []

def main():
    global handle,verified,allow_lr
    lib.hid_init()
    try:
        matches=find_device();check('unique_candidate_strings_and_joystick_usage',len(matches)==1)
        report['caps']=ro.descriptor_caps(matches[0])
        check('64_byte_input_output',report['caps']['input_bytes']==report['caps']['output_bytes']==64)
        handle=lib.hid_open_path(matches[0])
        if not handle:raise OSError('Cannot open exact candidate')
        check('readonly_candidate_magic',read_virtual(0x9000,8)==b'BCAP\x03\x00\x00\x01')
        verified=True
        for index,cmd in enumerate((1,2,3,2)):
            send(0x80,bytes([cmd]));packet=receive(0x81,lambda data:data[1]==cmd)
            check(f'USB_initialization_{index}_{cmd}',True)
            if cmd==1:usb_mac=packet[4:10]
        send(0x80,b'\x04')
        check('USB_ready_stage',stats()['usb_stage']==5)
        data=sub(2)
        check('device_info_and_consistent_MAC',data[13]==0x82 and data[17]==3 and data[19:25]==usb_mac[::-1])
        check('shipment_disable_volatile_ACK',sub(8,b'\0')[13]==0x80)
        check('shipment_enable_rejected',sub(8,b'\1')[13]==0)
        check('get_controller_state',sub(0)[13:16]==bytes.fromhex('800003'))
        check('trigger_elapsed_times_zero',sub(4)[13]==0x83)
        check('synthetic_serial',read_virtual(0x6000,16)==b'BPRO-RAM-0000002')
        sticks=read_virtual(0x603d,18)
        pairs=[xy(sticks[i:i+3]) for i in range(0,18,3)]
        report['synthetic_stick_pairs']=pairs
        check('left_calibration_max_center_min',pairs[:3]==[(1600,1600),(2048,2048),(1600,1600)])
        check('right_calibration_center_min_max',pairs[3:]==[(2048,2048),(1600,1600),(1600,1600)])
        check('calibration_ranges_within_12_bits',0<2048-1600<2048<2048+1600<4096)
        imu=read_virtual(0x6020,24)
        check('synthetic_IMU_no_zero_sensitivities',struct.unpack('<12h',imu)==(0,0,0,16384,16384,16384,0,0,0,13371,13371,13371))
        check('no_user_calibration_overrides',read_virtual(0x8010,29)==b'\xff'*29)
        check('virtual_boundary_no_wrap',read_virtual(0x60ff,2)==b'\xff\xff')
        check('maximum_address_read_safe',read_virtual(0xffffffff,1)==b'\xff')
        check('wrapping_address_rejected',sub(0x10,struct.pack('<IB',0xffffffff,2))[13]==0)
        check('oversized_read_rejected',sub(0x10,struct.pack('<IB',0x603d,30))[13]==0)
        rng=random.Random(0x20092350)
        start=time.perf_counter()
        for i in range(100):
            address=rng.randrange(0xa000,0x100000);size=rng.randrange(1,30)
            if read_virtual(address,size)!=b'\xff'*size:raise AssertionError(f'Unknown virtual region fixture {i}')
        report['100_roundtrips_elapsed_ms']=round((time.perf_counter()-start)*1000,3)
        check('100_parameterized_read_roundtrips',True)
        check('LED_state_write_ACK',sub(0x30,b'\x21')[13]==0x80)
        check('LED_state_readback',sub(0x31)[13:16]==b'\xb0\x31\x21')
        check('home_LED_volatile_noop',sub(0x38,b'\x01\xf0\xf0')[13]==0x80)
        check('IMU_enable_ACK',sub(0x40,b'\x01')[13]==0x80)
        check('IMU_sensitivity_ACK',sub(0x41,b'\x03\x00\x01\x01')[13]==0x80)
        check('IMU_bad_sensitivity_rejected',sub(0x41,b'\xff\x00\x00\x00')[13]==0)
        check('vibration_enable_ACK',sub(0x48,b'\x01')[13]==0x80)
        check('battery_voltage_reply',sub(0x50)[13:17]==bytes.fromhex('d0504006'))
        pair=sub(1,b'\x01'+b'ABCDEF')
        check('USB_pairing_compat_ACK_without_keys',pair[13:16]==b'\x81\x01\x03' and set(pair[16:])<={0})
        for cmd,label in ((7,'pairing_reset'),(0x11,'SPI_write'),(0x12,'SPI_erase'),(0x21,'NFC'),(0x7f,'unknown')):
            check(label+'_rejected',sub(cmd,b'\0'*8)[13]==0)
        check('unsupported_mode_rejected',sub(3,b'\x31')[13]==0)
        check('full_input_mode_ACK',sub(3,b'\x30')[13]==0x80)
        for _ in range(10):
            packet=receive(0x30)
            for i in range(3):
                if packet[13+12*i:25+12*i]!=bytes.fromhex('000000000010000000000000'):raise AssertionError('Static IMU sample mismatch')
        check('ten_neutral_reports_with_synthetic_static_IMU',True)
        check('mode2_enable_ACK',sub(0x40,b'\x02')[13]==0x80)
        check('mode2_state',stats()['imu']==2)
        timestamps=[]
        # Decode the wire report as a 288-bit integer, independently of C packing.
        for _ in range(160):
            pkt=receive(0x30,lambda p:(p[19]&3)==2)
            d=pkt[13:49];bits=int.from_bytes(d,'little')
            expected=(4096<<32)|(2<<48)|(3<<50)|(3<<282)
            mask=((1<<11)-1)<<271
            if bits & ~mask != expected:raise AssertionError('Stationary quaternion layout mismatch')
            timestamps.append((bits>>271)&2047)
        deltas=[(b-a)&2047 for a,b in zip(timestamps,timestamps[1:])]
        check('160_stationary_mode2_reports',True)
        check('mode2_timestamp_progression',all(10<=d<=100 for d in deltas))
        check('mode2_timestamp_wrap',any(b<a for a,b in zip(timestamps,timestamps[1:])))
        report['mode2_timestamps']=timestamps
        check('invalid_mode3_rejected',sub(0x40,b'\x03')[13]==0 and stats()['imu']==2)
        check('vibration_mode2_rejected',sub(0x48,b'\x02')[13]==0)
        check('mode0_disable_ACK',sub(0x40,b'\x00')[13]==0x80)
        receive(0x30,lambda p:p[13:49]==b'\0'*36)
        check('mode0_zero_motion',True)
        check('mode1_reenable_ACK',sub(0x40,b'\x01')[13]==0x80)
        receive(0x30,lambda p:p[13:49]==bytes.fromhex('000000000010000000000000')*3)
        check('mode1_restored_raw_layout',True)
        check('subreply_has_no_IMU_contamination',sub(0x31)[16:49]==b'\0'*33)
        check('registration_requires_IMU2',sub(0x30,b'\0')[13]==0x80 and read_virtual(0x903c,1)==b'\0')
        check('registration_IMU2_enable',sub(0x40,b'\x02')[13]==0x80)
        allow_lr=True
        started=time.perf_counter()
        check('registration_arm_ACK',sub(0x30,b'\0')[13]==0x80)
        check('registration_armed',read_virtual(0x903c,1)==b'\x01')
        observations=[]
        while time.perf_counter()-started<4.4:
            p=receive(0x30)
            observations.append((round(time.perf_counter()-started,4),p[3:6].hex()))
        pressed=[t for t,b in observations if b=='400040']
        check('only_L_and_R_together',bool(pressed))
        check('delayed_three_seconds',2.8<min(pressed)<3.2)
        check('hold_approximately_400ms',0.32<max(pressed)-min(pressed)<0.46)
        check('buttons_released_after_window',all(b=='000000' for t,b in observations if t>3.5))
        counts=read_virtual(0x9030,16)
        sent,down,up=struct.unpack_from('<III',counts)
        check('input_and_press_release_counters',sent>down>0 and up>0 and counts[12]==7)
        sub(0x30,b'\0')
        until=time.perf_counter()+3.5
        while time.perf_counter()<until:
            check_packet=receive(0x30)
            if check_packet[3:6]!=b'\0'*3:raise AssertionError('Unexpected repeated registration')
        check('repeated_LED_command_does_not_rearm',True)
        sub(3,b'\0')
        check('release_cancels_registration',read_virtual(0x903c,1)[0]&8)
        report['registration_observations']=observations
        report['registration_counts']={'sent':sent,'pressed':down,'released':up}
        allow_lr=False
        pattern=bytes.fromhex('1011223344556677')
        send(0x10,b'\0'+pattern)
        captured=read_virtual(0x9020,12)
        check('raw_rumble_capture',captured[:8]==pattern)
        time.sleep(0.15)
        check('rumble_expiry_cleared',read_virtual(0x9020,8)==b'\0'*8)
        send(0x80,b'\x05')
        report['final_stats']=stats()
        check('USB_release_stops_stream',report['final_stats']['mode']==0 and report['final_stats']['usb_stage']==0)
        check('no_queue_overflow',report['final_stats']['overflow']==0)
        trace=read_range(0x9100,256);report['trace_raw_hex']=trace.hex()
        from pico_capture_log import decode_slots
        send(0x80,b'\xfdSNAPLOG3')
        image=read_range(0xa000,4096)
        decoded=decode_slots(image)
        capture=decoded['newest']
        report['capture_summary']={k:v for k,v in capture.items() if k!='events'}
        check('RAM_journal_CRC_and_marker',capture['crc_valid'] and capture['no_flash_marker']==1)
        check('journal_first_and_last_preserved',capture['first_count']==24 and capture['tail_count']==24 and capture['dropped_middle_events']>0)
        check('journal_captured_raw_rumble',any(e['report_id']=='10' and e['raw_hex'][4:20]==pattern.hex() for e in capture['events']))
        check('pairing_arguments_redacted',any(e['pairing_arguments_redacted'] and bytes.fromhex(e['raw_hex'])[11]==1 and set(bytes.fromhex(e['raw_hex'])[12:])<={0} for e in capture['events']))
        capture_file=ro.ROOT/'outputs'/'pico-capture-v033-ram-journal.bin'
        capture_file.write_bytes(image)
        capture_file.with_suffix('.json').write_text(json.dumps(decoded,indent=2),encoding='utf-8')
        report['status']='PASSED_PC_CAPTURE_RAM_DRYRUN'
    except BaseException as exc:
        report['status']='INCOMPLETE';report['error']=f'{type(exc).__name__}: {exc}'
    finally:
        if handle:
            if verified:
                try:
                    send(0x80,b'\xfeRESETLAB');report['restore_original_requested']=True
                except BaseException as exc:report['restore_request_error']=str(exc)
            lib.hid_close(handle)
        lib.hid_exit()
        output=ro.ROOT/'outputs'/('pico-capture-v033-ram-test-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'.json')
        output.write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report,indent=2));print('REPORT '+str(output))
    return 0 if report['status']=='PASSED_PC_CAPTURE_RAM_DRYRUN' else 1

if __name__=='__main__':sys.exit(main())
