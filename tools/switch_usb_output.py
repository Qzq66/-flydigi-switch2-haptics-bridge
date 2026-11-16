"""Restricted 0x10 writer, separate from the receive-only module. No feature/config API."""
import ctypes as c
from ctypes import wintypes as w
from switch_usb_readonly import libraries, Overlapped, Attributes, Caps
from switch_rumble_packet import validate


def inspect_output_reports(device):
    """Read Windows-cached HID capabilities; does not issue an output report."""
    kernel, hid, _ = libraries()
    handle = kernel.CreateFileW(device['path'], 0, 3, None, 3, 0, None)
    if handle == c.c_void_p(-1).value: raise OSError('Cannot read output metadata')
    prep = c.c_void_p()
    try:
        if not hid.HidD_GetPreparsedData(handle, c.byref(prep)): raise OSError('No preparsed HID data')
        caps = Caps()
        if hid.HidP_GetCaps(prep, c.byref(caps)) != 0x110000: raise OSError('HID capabilities unavailable')
        entries = []
        # Both structures are 72 bytes in the installed Windows SDK hidpi.h.
        for name, count, kind in (('HidP_GetValueCaps', caps.output_values, 'value'),
                                  ('HidP_GetButtonCaps', caps.output_buttons, 'button')):
            if not count: continue
            if count > 1024: raise ValueError('Unexpected output capability count')
            buffer = c.create_string_buffer(count*72)
            length = w.USHORT(count)
            fn = getattr(hid, name)
            fn.argtypes = [c.c_int, c.c_void_p, c.POINTER(w.USHORT), c.c_void_p]
            fn.restype = c.c_long
            if fn(1, buffer, c.byref(length), prep) != 0x110000: raise OSError('Output capabilities query failed')
            for index in range(length.value):
                data = buffer.raw[index*72:(index+1)*72]
                item = dict(report_id=data[2], usage_page=int.from_bytes(data[:2], 'little'), kind=kind)
                if kind == 'value':
                    item.update(bit_size=int.from_bytes(data[18:20], 'little'),
                                report_count=int.from_bytes(data[20:22], 'little'))
                entries.append(item)
        return entries
    finally:
        if prep: hid.HidD_FreePreparsedData(prep)
        kernel.CloseHandle(handle)


class Writer:
    def __init__(self, device):
        if device['vid'] != 0x057e or device['pid'] != 0x2009 or device['output_len'] != 64:
            raise ValueError('Unexpected Switch USB endpoint')
        if 0x10 not in device.get('declared_output_ids', []):
            raise ValueError('Rumble report 0x10 must be declared by the current HID descriptor')
        if not device['path'].lower().startswith('\\\\?\\hid#vid_057e&pid_2009'):
            raise ValueError('Physical USB target required')
        self.kernel, hid, _ = libraries()
        self.kernel.WriteFile.argtypes = [w.HANDLE, c.c_void_p, w.DWORD, c.POINTER(w.DWORD), c.POINTER(Overlapped)]
        self.kernel.WriteFile.restype = w.BOOL
        self.handle = self.kernel.CreateFileW(device['path'], 0x40000000, 3, None, 3, 0x40000000, None)
        if self.handle == c.c_void_p(-1).value:
            self.handle = None
            raise OSError(c.get_last_error(), 'Cannot open exact USB output endpoint')
        attr = Attributes(size=c.sizeof(Attributes))
        if not hid.HidD_GetAttributes(self.handle, c.byref(attr)) or (attr.vid, attr.pid) != (0x057e, 0x2009):
            self.close(); raise ValueError('Opened endpoint identity changed')

    def send(self, packet, timeout_ms=4):
        if not isinstance(timeout_ms, int) or not 1 <= timeout_ms <= 1000:
            raise ValueError('timeout_ms must be 1..1000')
        packet = validate(packet)
        event = self.kernel.CreateEventW(None, True, False, None)
        if not event: raise OSError('Cannot allocate bounded output event')
        overlap = Overlapped(event=event)
        buf = c.create_string_buffer(packet)
        pending = False
        try:
            ok = self.kernel.WriteFile(self.handle, buf, len(packet), None, c.byref(overlap))
            if not ok and c.get_last_error() != 997:
                raise OSError(c.get_last_error(), 'USB output rejected')
            pending = True
            wait = self.kernel.WaitForSingleObject(event, timeout_ms)
            if wait != 0: raise TimeoutError('USB output did not complete within %dms' % timeout_ms)
            size = w.DWORD()
            if not self.kernel.GetOverlappedResult(self.handle, c.byref(overlap), c.byref(size), False):
                raise OSError(c.get_last_error(), 'USB output completion failed')
            pending = False
            if size.value != len(packet): raise OSError('Short USB output write')
        finally:
            if pending:
                self.kernel.CancelIoEx(self.handle, c.byref(overlap))
                size = w.DWORD()
                self.kernel.GetOverlappedResult(self.handle, c.byref(overlap), c.byref(size), True)
            self.kernel.CloseHandle(event)

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle); self.handle = None


if __name__ == '__main__':
    import json
    from switch_usb_readonly import enumerate_usb
    devices = enumerate_usb()
    if len(devices) != 1: raise ValueError('Exactly one USB Switch-mode gamepad required')
    print(json.dumps(inspect_output_reports(devices[0])))
