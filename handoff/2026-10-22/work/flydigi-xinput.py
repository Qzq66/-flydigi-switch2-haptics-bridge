"""Select an XInput slot by VID/PID; sending vibration is explicit only."""
import ctypes as C
from ctypes import wintypes as W
import json

class Gamepad(C.Structure):
    _fields_=[('buttons',W.WORD),('lt',W.BYTE),('rt',W.BYTE),('lx',C.c_short),('ly',C.c_short),('rx',C.c_short),('ry',C.c_short)]
class Vibration(C.Structure):
    _fields_=[('left',W.WORD),('right',W.WORD)]
class Caps(C.Structure):
    _fields_=[('type',W.BYTE),('subtype',W.BYTE),('flags',W.WORD),('gamepad',Gamepad),('vibration',Vibration)]
class CapsEx(C.Structure):
    _fields_=[('caps',Caps),('vid',W.WORD),('pid',W.WORD),('version',W.WORD),('unknown1',W.WORD),('unknown2',W.DWORD)]

dll=C.WinDLL('xinput1_4.dll')
get_caps=C.WINFUNCTYPE(W.DWORD,W.DWORD,W.DWORD,W.DWORD,C.POINTER(CapsEx))((108,dll))
set_state=dll.XInputSetState
set_state.argtypes=[W.DWORD,C.POINTER(Vibration)]
set_state.restype=W.DWORD

def slots():
    found=[]
    for index in range(4):
        caps=CapsEx()
        rc=get_caps(1,index,0,C.byref(caps))
        if rc==0: found.append(dict(index=index,vid=f'{caps.vid:04X}',pid=f'{caps.pid:04X}',version=caps.version))
    return found

def flydigi_index():
    found=[entry['index'] for entry in slots() if entry['vid']=='37D7' and entry['pid']=='2502']
    if len(found)!=1: raise ValueError('Exactly one matching Flydigi XInput slot required')
    return found[0]

def set_levels(index,left,right):
    if not 0<=left<=4096 or not 0<=right<=4096: raise ValueError('Rumble cap exceeded')
    if flydigi_index()!=index: raise ValueError('Matching slot changed; refusing output')
    rc=set_state(index,C.byref(Vibration(left,right)))
    if rc: raise OSError(f'XInputSetState status {rc}')

if __name__=='__main__':print(json.dumps(dict(slots=slots(),configuration_writes=0,vibration_commands=0),indent=2))
