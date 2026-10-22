"""Exercises only the CAFE:4010 vendor HID laboratory firmware on this PC."""
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
lib.hid_get_feature_report.argtypes=[C.c_void_p,C.c_void_p,C.c_size_t]
lib.hid_get_feature_report.restype=C.c_int
report=dict(started_at=datetime.datetime.now().astimezone().isoformat(),checks=[],persistent_commands=0,physical_output=False,switch2_tested=False)
handle=None

def check(name,condition):
    report['checks'].append(dict(name=name,passed=bool(condition)))
    if not condition:raise AssertionError(name)

def send(rid,payload=b''):
    if rid not in (1,0x10,0x80,0xf0) or len(payload)>63:raise ValueError('Unapproved lab packet')
    data=(bytes([rid])+payload).ljust(64,b'\0')
    tx=C.create_string_buffer(data,64)
    if lib.hid_write(handle,tx,64)!=64:raise OSError('Lab HID write failed')

def receive(wanted,timeout=1):
    end=time.perf_counter()+timeout
    while time.perf_counter()<end:
        buf=C.create_string_buffer(64)
        n=lib.hid_read_timeout(handle,buf,64,50)
        if n<0:raise OSError('Lab HID read failed')
        if not n:continue
        data=buf.raw[:n]
        if data[0]==0x30:
            if data[3:6]!=b'\0'*3 or data[6:12]!=bytes.fromhex('000880000880'):
                raise AssertionError('Non-neutral controller state')
        if data[0]==wanted:return data
    raise TimeoutError(f'No report {wanted:02X}')

def stats():
    buf=C.create_string_buffer(64);buf[0]=b'\xf1'
    n=lib.hid_get_feature_report(handle,buf,64)
    if n!=64 or buf.raw[1:5]!=b'PLAB':raise ValueError('Not laboratory firmware')
    p=buf.raw[1:]
    return dict(version=p[4],mode=p[5],rumble_live=bool(p[6]),no_flash=p[7],
                **dict(zip(('received','replies','rumble_count','rejected','overflow','short_packets'),struct.unpack_from('<6I',p,8))),last_rumble=p[32:40].hex())

def sub(cmd,args=b''):
    send(1,b'\0'+bytes.fromhex('0001404000014040')+bytes([cmd])+args)
    data=receive(0x21)
    if data[14]!=cmd:raise AssertionError('Mismatched subcommand reply')
    return data

def main():
    global handle
    lib.hid_init()
    try:
        # Windows can take several seconds to install the first HID identity.
        # Wait only for the exact laboratory device; never fall back to another HID.
        discovery_deadline=time.perf_counter()+20
        matches=[]
        while time.perf_counter()<discovery_deadline:
            head=lib.hid_enumerate(0xcafe,0x4010);matches=[]
            try:
                node=head
                while node:
                    d=node.contents
                    if d.usage_page==0xff60 and d.product_string=='Bridge Protocol Lab RAM' and d.serial_number=='PLAB-RP2350-LOCAL-01':matches.append(bytes(d.path))
                    node=d.next
            finally:
                if head:lib.hid_free_enumeration(head)
            if matches:break
            time.sleep(0.2)
        check('single_exact_lab_identity',len(matches)==1)
        caps=ro.descriptor_caps(matches[0]);report['caps']=caps
        check('64_byte_in_out_feature',all(caps[k]==64 for k in ('input_bytes','output_bytes','feature_bytes')))
        handle=lib.hid_open_path(matches[0])
        if not handle:raise OSError('Cannot open lab device')
        initial=stats();report['initial']=initial
        check('SRAM_build_marker',initial['no_flash']==1)
        for cmd in (1,2,3,2):
            send(0x80,bytes([cmd]));data=receive(0x81)
            check(f'usb_handshake_{cmd}_{len(report["checks"])}',data[1]==cmd and (cmd!=1 or data[2:4]==b'\0\x03'))
        send(0x80,b'\x04')
        data=sub(2);check('device_info_type',data[13]==0x82 and data[17]==3)
        rng=random.Random(0x2350)
        for index in range(100):
            addr=rng.randrange(0,0x100000000);size=rng.randrange(0,30)
            args=struct.pack('<IB',addr,size)
            data=sub(0x10,args)
            if data[13]!=0x90 or data[15:20]!=args or data[20:20+size]!=b'\xff'*size:raise AssertionError(f'Virtual SPI fixture {index}')
        check('100_distinct_virtual_SPI_read_roundtrips',True)
        check('oversized_virtual_read_NACK',sub(0x10,struct.pack('<IB',0x603d,30))[13]==0)
        check('SPI_write_NACK',sub(0x11,b'\0'*8)[13]==0)
        check('SPI_erase_NACK',sub(0x12,b'\0'*8)[13]==0)
        check('unsupported_subcommand_NACK',sub(0x7f)[13]==0)
        check('unsupported_input_mode_NACK',sub(3,b'\x31')[13]==0)
        check('full_input_mode_ACK',sub(3,b'\x30')[13]==0x80)
        for _ in range(10):receive(0x30)
        check('ten_neutral_full_input_reports',True)
        sub(3,b'\0')
        pattern=bytes.fromhex('1011223344556677')
        send(0x10,b'\0'+pattern)
        active=stats();report['rumble_active']=active
        check('raw_rumble_capture_without_actuation',active['rumble_live'] and active['last_rumble']==pattern.hex())
        time.sleep(0.15)
        expired=stats();report['rumble_expired']=expired
        check('stale_rumble_cleared',not expired['rumble_live'] and expired['last_rumble']=='00'*8)
        check('no_reply_queue_overflow',expired['overflow']==0)
        report['status']='PASSED_PC_PROTOCOL_SUBSET'
    except BaseException as exc:
        report['status']='INCOMPLETE';report['error']=f'{type(exc).__name__}: {exc}'
    finally:
        if handle:
            try:
                send(0xf0,b'RESETLAB');report['restore_original_firmware_requested']=True
            except BaseException as exc:report['restore_request_error']=str(exc)
            lib.hid_close(handle)
        lib.hid_exit()
        output=ro.ROOT/'outputs'/('pico-protocol-lab-test-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'.json')
        output.write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report,indent=2));print('REPORT '+str(output))
    return 0 if report['status']=='PASSED_PC_PROTOCOL_SUBSET' else 1

if __name__=='__main__':sys.exit(main())
