"""Read-only XInput enumeration; never calls SetState or changes mappings."""
import ctypes as C,json
class Gamepad(C.Structure):
    _fields_=[('buttons',C.c_ushort),('lt',C.c_ubyte),('rt',C.c_ubyte),('lx',C.c_short),('ly',C.c_short),('rx',C.c_short),('ry',C.c_short)]
class State(C.Structure):_fields_=[('packet',C.c_ulong),('gamepad',Gamepad)]
lib=C.WinDLL('XInput1_4.dll');lib.XInputGetState.argtypes=[C.c_uint,C.POINTER(State)];lib.XInputGetState.restype=C.c_uint
def read(slot):
    state=State();code=lib.XInputGetState(slot,C.byref(state))
    if code==1167:return None
    if code:raise OSError(code,'XInputGetState failed')
    return state
def connected():return [i for i in range(4) if read(i) is not None]
if __name__=='__main__':print(json.dumps(dict(readonly=True,connected_slots=connected())))
