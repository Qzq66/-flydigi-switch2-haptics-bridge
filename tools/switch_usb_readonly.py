"""Native Windows HID reader. Exact USB 057e:2009 gamepad only; no write APIs."""
import ctypes as c
from ctypes import wintypes as w


class Guid(c.Structure):
    _fields_ = [('a', w.DWORD), ('b', w.WORD), ('d', w.WORD), ('e', c.c_ubyte * 8)]


class Interface(c.Structure):
    _fields_ = [('size', w.DWORD), ('guid', Guid), ('flags', w.DWORD), ('reserved', c.c_size_t)]


class Attributes(c.Structure):
    _fields_ = [('size', w.DWORD), ('vid', w.WORD), ('pid', w.WORD), ('version', w.WORD)]


class Caps(c.Structure):
    _fields_ = [(n, w.WORD) for n in ('usage', 'page', 'input_len', 'output_len', 'feature_len')] + [
        ('reserved', w.WORD * 17)] + [(n, w.WORD) for n in (
        'collections', 'input_buttons', 'input_values', 'input_indices', 'output_buttons',
        'output_values', 'output_indices', 'feature_buttons', 'feature_values', 'feature_indices')]


class Overlapped(c.Structure):
    _fields_ = [('internal', c.c_size_t), ('internal_high', c.c_size_t), ('offset', w.DWORD),
                ('offset_high', w.DWORD), ('event', w.HANDLE)]


def libraries():
    kernel, hid, setup = c.WinDLL('kernel32', use_last_error=True), c.WinDLL('hid'), c.WinDLL('setupapi')
    def bind(lib, name, result, *args):
        fn = getattr(lib, name); fn.restype = result; fn.argtypes = list(args)
    bind(hid, 'HidD_GetHidGuid', None, c.POINTER(Guid))
    bind(hid, 'HidD_GetAttributes', w.BOOL, w.HANDLE, c.POINTER(Attributes))
    bind(hid, 'HidD_GetProductString', w.BOOL, w.HANDLE, c.c_void_p, w.ULONG)
    bind(hid, 'HidD_GetPreparsedData', w.BOOL, w.HANDLE, c.POINTER(c.c_void_p))
    bind(hid, 'HidD_FreePreparsedData', w.BOOL, c.c_void_p)
    bind(hid, 'HidP_GetCaps', c.c_long, c.c_void_p, c.POINTER(Caps))
    bind(setup, 'SetupDiGetClassDevsW', w.HANDLE, c.POINTER(Guid), w.LPCWSTR, w.HWND, w.DWORD)
    bind(setup, 'SetupDiEnumDeviceInterfaces', w.BOOL, w.HANDLE, c.c_void_p, c.POINTER(Guid), w.DWORD, c.POINTER(Interface))
    bind(setup, 'SetupDiGetDeviceInterfaceDetailW', w.BOOL, w.HANDLE, c.POINTER(Interface), c.c_void_p, w.DWORD, c.POINTER(w.DWORD), c.c_void_p)
    bind(setup, 'SetupDiDestroyDeviceInfoList', w.BOOL, w.HANDLE)
    bind(kernel, 'CreateFileW', w.HANDLE, w.LPCWSTR, w.DWORD, w.DWORD, c.c_void_p, w.DWORD, w.DWORD, w.HANDLE)
    bind(kernel, 'CloseHandle', w.BOOL, w.HANDLE)
    bind(kernel, 'CreateEventW', w.HANDLE, c.c_void_p, w.BOOL, w.BOOL, w.LPCWSTR)
    bind(kernel, 'ResetEvent', w.BOOL, w.HANDLE)
    bind(kernel, 'ReadFile', w.BOOL, w.HANDLE, c.c_void_p, w.DWORD, c.POINTER(w.DWORD), c.POINTER(Overlapped))
    bind(kernel, 'GetOverlappedResult', w.BOOL, w.HANDLE, c.POINTER(Overlapped), c.POINTER(w.DWORD), w.BOOL)
    bind(kernel, 'WaitForSingleObject', w.DWORD, w.HANDLE, w.DWORD)
    bind(kernel, 'CancelIoEx', w.BOOL, w.HANDLE, c.POINTER(Overlapped))
    return kernel, hid, setup


def enumerate_usb():
    kernel, hid, setup = libraries()
    guid = Guid(); hid.HidD_GetHidGuid(c.byref(guid))
    devs = setup.SetupDiGetClassDevsW(c.byref(guid), None, None, 0x12)
    if devs == c.c_void_p(-1).value: raise OSError('Cannot enumerate HID interfaces')
    found = []
    try:
        index = 0
        while True:
            item = Interface(size=c.sizeof(Interface))
            if not setup.SetupDiEnumDeviceInterfaces(devs, None, c.byref(guid), index, c.byref(item)): break
            index += 1
            needed = w.DWORD()
            setup.SetupDiGetDeviceInterfaceDetailW(devs, c.byref(item), None, 0, c.byref(needed), None)
            if needed.value < 8 or needed.value > 8192: continue
            buf = c.create_string_buffer(needed.value)
            c.cast(buf, c.POINTER(w.DWORD))[0] = 8 if c.sizeof(c.c_void_p) == 8 else 6
            if not setup.SetupDiGetDeviceInterfaceDetailW(devs, c.byref(item), buf, needed.value, None, None): continue
            path = c.wstring_at(c.addressof(buf) + 4)
            # Bluetooth HID paths use different prefixes. Never open unrelated devices.
            if not path.lower().startswith('\\\\?\\hid#vid_057e&pid_2009'): continue
            handle = kernel.CreateFileW(path, 0, 3, None, 3, 0, None)
            if handle == c.c_void_p(-1).value: continue
            try:
                attr = Attributes(size=c.sizeof(Attributes)); caps = Caps(); prep = c.c_void_p()
                if not hid.HidD_GetAttributes(handle, c.byref(attr)) or (attr.vid, attr.pid) != (0x057e, 0x2009): continue
                if not hid.HidD_GetPreparsedData(handle, c.byref(prep)): continue
                try:
                    if hid.HidP_GetCaps(prep, c.byref(caps)) != 0x110000: continue
                finally: hid.HidD_FreePreparsedData(prep)
                name = c.create_unicode_buffer(128)
                hid.HidD_GetProductString(handle, name, c.sizeof(name))
                if name.value.startswith('Bridge Pro'): continue
                if caps.page == 1 and caps.usage in (4, 5) and 1 <= caps.input_len <= 1024:
                    found.append(dict(path=path, product=name.value, vid=attr.vid, pid=attr.pid,
                                      usage_page=caps.page, usage=caps.usage, input_len=caps.input_len,
                                      output_len=caps.output_len, feature_len=caps.feature_len))
            finally: kernel.CloseHandle(handle)
    finally: setup.SetupDiDestroyDeviceInfoList(devs)
    return found


class Reader:
    def __init__(self, device):
        self.kernel, _, _ = libraries(); self.handle = None; self.event = None; self.pending = False
        self.length = device['input_len']; self.buffer = c.create_string_buffer(self.length)
        handle = self.kernel.CreateFileW(device['path'], 0x80000000, 3, None, 3, 0x40000000, None)
        if handle == c.c_void_p(-1).value: raise OSError(c.get_last_error(), 'Read-only HID open failed')
        self.handle = handle
        self.event = self.kernel.CreateEventW(None, True, False, None)
        if not self.event:
            self.close(); raise OSError('Cannot allocate read event')
        self.overlapped = Overlapped(event=self.event)

    def poll(self):
        if not self.pending:
            self.kernel.ResetEvent(self.event)
            ok = self.kernel.ReadFile(self.handle, self.buffer, self.length, None, c.byref(self.overlapped))
            if not ok and c.get_last_error() != 997: raise OSError(c.get_last_error(), 'HID read failed')
            self.pending = True
        state = self.kernel.WaitForSingleObject(self.event, 0)
        if state == 258: return None
        if state != 0: raise OSError('Read event wait failed')
        size = w.DWORD()
        if not self.kernel.GetOverlappedResult(self.handle, c.byref(self.overlapped), c.byref(size), False):
            raise OSError(c.get_last_error(), 'HID completion failed')
        self.pending = False
        return bytes(self.buffer.raw[:size.value])

    def close(self):
        if self.handle:
            if self.pending:
                self.kernel.CancelIoEx(self.handle, c.byref(self.overlapped))
                # Buffer remains alive until the cancelled operation has completed.
                size = w.DWORD()
                self.kernel.GetOverlappedResult(self.handle, c.byref(self.overlapped), c.byref(size), True)
                self.pending = False
            self.kernel.CloseHandle(self.handle); self.handle = None
        if self.event: self.kernel.CloseHandle(self.event); self.event = None


if __name__ == '__main__':
    import json
    print(json.dumps([{k: v for k, v in x.items() if k != 'path'} for x in enumerate_usb()], ensure_ascii=True))
