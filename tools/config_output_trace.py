"""Separate explicit volatile-output trace; read-only tracer is unchanged."""
import ctypes as C
from config_read_trace import ReadOnlyTrace
class VolatileOutputTrace(ReadOnlyTrace):
    def hid_write(self,handle,buffer,size):
        raw=C.string_at(buffer,size)
        if len(raw)!=33 or raw[:3]!=bytes((0,0x5a,0xa5)):raise ValueError('Invalid trace packet')
        if raw[3] not in (0x53,0x57):return super().hid_write(handle,buffer,size)
        if raw[32]!=sum(raw[3:32])&255:raise ValueError('Output checksum mismatch')
        if raw[3]==0x53:
            n=raw[4]-2;payload=raw[5:5+n]
            if payload not in (bytes.fromhex('0112024000'),bytes.fromhex('011200')) or any(raw[5+n:32]):raise ValueError('Unapproved runtime mode')
        else:
            if raw[4]!=27 or raw[5] not in (0x98,0x80) or raw[30:32]!=bytes(2):raise ValueError('Unknown stream shape')
            for i in range(8):
                pos=6+3*i
                if raw[pos]!=128 or abs(raw[pos+1]-128)>9 or abs(raw[pos+2]-128)>9:raise ValueError('Sample bound')
        self.reserve(size);start=self.clock();result=self.lib.hid_write(handle,buffer,size)
        self.events.append(dict(kind='volatile_output',start=start,end=self.clock(),raw_hex=raw.hex(),result=result));self.raw_bytes+=size;return result
