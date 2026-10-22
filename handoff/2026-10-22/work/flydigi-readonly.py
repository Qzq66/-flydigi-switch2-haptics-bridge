"""Read-only GPA6 identity/capability/configuration queries. No setting commands."""
import ctypes as C
from ctypes import wintypes as W
import json
import pathlib
import struct
import time
import zlib

ROOT = pathlib.Path(__file__).resolve().parents[1]

class HidInfo(C.Structure):
    pass

HidInfo._fields_ = [
    ('path', C.c_char_p), ('vendor_id', C.c_ushort), ('product_id', C.c_ushort),
    ('serial_number', C.c_wchar_p), ('release_number', C.c_ushort),
    ('manufacturer_string', C.c_wchar_p), ('product_string', C.c_wchar_p),
    ('usage_page', C.c_ushort), ('usage', C.c_ushort),
    ('interface_number', C.c_int), ('next', C.POINTER(HidInfo)),
]

class Caps(C.Structure):
    _fields_ = [('usage', W.USHORT), ('usage_page', W.USHORT),
                ('input_length', W.USHORT), ('output_length', W.USHORT),
                ('feature_length', W.USHORT), ('reserved', W.USHORT * 17),
                ('counts', W.USHORT * 10)]

def descriptor_caps(path):
    kernel = C.WinDLL('kernel32', use_last_error=True)
    hid = C.WinDLL('hid', use_last_error=True)
    kernel.CreateFileW.argtypes = [W.LPCWSTR,W.DWORD,W.DWORD,C.c_void_p,W.DWORD,W.DWORD,W.HANDLE]
    kernel.CreateFileW.restype = W.HANDLE
    kernel.CloseHandle.argtypes = [W.HANDLE]
    hid.HidD_GetPreparsedData.argtypes = [W.HANDLE,C.POINTER(C.c_void_p)]
    hid.HidD_GetPreparsedData.restype = W.BOOLEAN
    hid.HidD_FreePreparsedData.argtypes = [C.c_void_p]
    hid.HidP_GetCaps.argtypes = [C.c_void_p,C.POINTER(Caps)]
    hid.HidP_GetCaps.restype = W.LONG
    handle = kernel.CreateFileW(path.decode(),0,3,None,3,0,None)
    if handle == C.c_void_p(-1).value:
        raise OSError(C.get_last_error(), 'Read-only descriptor open failed')
    data = C.c_void_p()
    try:
        if not hid.HidD_GetPreparsedData(handle,C.byref(data)):
            raise OSError('Preparsed descriptor unavailable')
        caps = Caps()
        if hid.HidP_GetCaps(data,C.byref(caps)) != 0x110000:
            raise OSError('HID descriptor decode failed')
        return dict(input_bytes=caps.input_length,output_bytes=caps.output_length,
                    feature_bytes=caps.feature_length)
    finally:
        if data: hid.HidD_FreePreparsedData(data)
        kernel.CloseHandle(handle)

lib = C.CDLL(r'D:\Engine\firmware\hidapi.dll')
lib.hid_init.restype = C.c_int
lib.hid_enumerate.argtypes = [C.c_ushort,C.c_ushort]
lib.hid_enumerate.restype = C.POINTER(HidInfo)
lib.hid_free_enumeration.argtypes = [C.POINTER(HidInfo)]
lib.hid_open_path.argtypes = [C.c_char_p]
lib.hid_open_path.restype = C.c_void_p
lib.hid_write.argtypes = [C.c_void_p,C.c_void_p,C.c_size_t]
lib.hid_write.restype = C.c_int
lib.hid_read_timeout.argtypes = [C.c_void_p,C.c_void_p,C.c_size_t,C.c_int]
lib.hid_read_timeout.restype = C.c_int
lib.hid_close.argtypes = [C.c_void_p]
lib.hid_exit.restype = C.c_int

class Reader:
    ALLOWED = frozenset((0x01,0x04,0x07,0xA1,0xA3))
    def __init__(self, path, output_bytes):
        self.handle = lib.hid_open_path(path)
        if not self.handle: raise OSError('Vendor interface open failed')
        self.output_bytes = output_bytes
        self.query_counts = {}

    def close(self):
        if self.handle: lib.hid_close(self.handle); self.handle = None

    def validate_query(self, command, payload):
        if command not in self.ALLOWED: raise ValueError('Non-read-only command refused')
        if command == 0xA3 and (len(payload) < 2 or payload[0] not in (0,1) or payload[1] not in (1,4,5,6)):
            raise ValueError('Only QUERY/READ configuration RAM is permitted')
        if command != 0xA3 and payload: raise ValueError('Unexpected read payload')

    def ask(self, command, payload=b'', *, reply_size, modern=False):
        self.validate_query(command,payload)
        private = bytearray(32)
        private[:4] = bytes((0x5a,0xa5,command,len(payload)+2))
        private[4:4+len(payload)] = payload
        private[31] = sum(private[2:31]) & 255
        packet = bytes((0,)) + private
        if self.output_bytes < len(packet): raise ValueError('Output report too short')
        packet = packet.ljust(self.output_bytes,b'\0')
        tx = C.create_string_buffer(packet,len(packet))
        if lib.hid_write(self.handle,tx,len(packet)) != len(packet):
            raise OSError('Read query transport write failed')
        self.query_counts[f'{command:02X}'] = self.query_counts.get(f'{command:02X}',0)+1
        deadline = time.monotonic()+1.2
        rx = C.create_string_buffer(512)
        while time.monotonic() < deadline:
            count = lib.hid_read_timeout(self.handle,rx,len(rx),100)
            if count < 0: raise OSError('HID read failed')
            if not count: continue
            body = rx.raw[:count]
            if body[:3] == b'\0\x5a\xa5': body = body[1:]
            if body[:3] != bytes((0x5a,0xa5,command)): continue
            start = 3 if modern else 5
            error = not modern and len(body)>3 and body[3]==0
            size = 1 if error else (reply_size(body[start:]) if callable(reply_size) else reply_size)
            end = start+size
            for check in dict.fromkeys((end,31,len(body)-1)):
                if check < end or check >= len(body): continue
                if any(body[end:check]) or any(body[check+1:]): continue
                if sum(body[2:check]) & 255 != body[check]: continue
                if error: raise ValueError(f'Read query refused: {body[start]}')
                if not modern and body[3:5] != b'\x01\x00': raise ValueError('Unexpected packet count')
                return body[start:end]
            raise ValueError(f'Invalid read reply checksum/layout for {command:02X}')
        raise TimeoutError(f'No reply to read-only query {command:02X}')

    def state(self):
        return struct.unpack('<B5H',self.ask(0xA1,reply_size=11))

    def motor_info(self):
        p = self.ask(0xA3,b'\x01\x06',reply_size=10,modern=True)
        if p[:3]!=b'\x01\x00\x06' or p[3]>3: raise ValueError('Invalid motor RAM header')
        return struct.unpack('<BHI',p[3:])

    def motor_snapshot(self):
        before = self.motor_info()
        slot,total,crc = before
        if total>4096: raise ValueError('Motor RAM exceeds read limit')
        data = bytearray()
        for index in range((total+15)//16):
            p = self.ask(0xA3,bytes((0,6,index,16)),reply_size=lambda p:8+p[7],modern=True)
            header = struct.pack('<4BHB',0,0,6,slot,total,index)
            count = min(16,total-len(data))
            if p[:7]!=header or p[7] not in (count,16): raise ValueError('RAM chunk mismatch')
            data.extend(p[8:8+count])
        if self.motor_info()!=before or zlib.crc32(data)!=crc: raise ValueError('RAM fingerprint mismatch')
        return dict(active_slot=slot,bytes=total,crc32=f'{crc:08X}',raw_hex=data.hex().upper(),layout=data[0] if data else None)

def main():
    result = dict(read_only=True,configuration_writes=0,streaming_frames=0,interfaces=[])
    pointer = None
    reader = None
    try:
        if lib.hid_init(): raise OSError('hidapi init failed')
        pointer = lib.hid_enumerate(0x37D7,0x2502)
        node = pointer
        candidates = []
        while node:
            d = node.contents
            row = dict(vid='37D7',pid='2502',usage_page=f'{d.usage_page:04X}',usage=f'{d.usage:04X}',interface=d.interface_number,product=d.product_string,release=d.release_number)
            if d.usage_page == 0xFFA0:
                row.update(descriptor_caps(d.path))
                candidates.append((d.path,row))
            result['interfaces'].append(row)
            node = d.next
        if len(candidates)!=1: raise ValueError(f'Expected one FFA0 interface, found {len(candidates)}')
        path,row = candidates[0]
        reader = Reader(path,row['output_bytes'])
        info = reader.ask(1,reply_size=25)
        flags = info[24]
        result['device'] = dict(device_type=f'{info[0]:02X}',connection_mode=info[1],connection={1:'wired',2:'dongle'}.get(info[1],'unknown'),battery_level_code=info[6]&15,firmware_words=list(struct.unpack('>7H',info[10:24])),features_raw=f'{flags:02X}',haptic_grip=bool(flags&128),trigger_haptic=bool(flags&16))
        result['format_versions'] = list(struct.unpack('<3H',reader.ask(7,reply_size=6)))
        state_before = reader.state()
        result['config_state_before'] = state_before
        result['motor_snapshot'] = reader.motor_snapshot()
        result['config_state_after'] = reader.state()
        result['config_state_unchanged'] = tuple(result['config_state_after'])==state_before
        result['motor_fingerprint_unchanged'] = reader.motor_info() == (result['motor_snapshot']['active_slot'],result['motor_snapshot']['bytes'],int(result['motor_snapshot']['crc32'],16))
        result['status']='READ_ONLY_QUERIES_PASSED'
    except Exception as exc:
        result['status']='STOPPED'
        result['error']=f'{type(exc).__name__}: {exc}'
    finally:
        if reader:
            result['read_query_counts']=reader.query_counts
            reader.close()
        if pointer: lib.hid_free_enumeration(pointer)
        lib.hid_exit()
        output=ROOT/'outputs'/'flydigi-readonly-report.json'
        output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
