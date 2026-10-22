# SPDX-License-Identifier: GPL-2.0-only
# Python adaptation of MissionControl switch_hd_rumble_decoder.cpp/types.hpp.
# Copyright (c) 2020-2026 ndeadly; adaptation 2026 for this workspace.
# Reference commit: 71bbe2d4e97d618775b5a3e2f91bfeaf52d8b75e.
# GPL v2 license: references/missioncontrol-LICENSE. No warranty.
"""Stateful HD rumble decoder, offline only. No USB, HID or actuator access.

Fields become unknown across missing capture events; delta packets cannot recover
missing state. Zero-type packets contain no new samples and do not reset state.
"""
import json,pathlib,argparse

COMMANDS=[(1,1,0,0)]
COMMANDS += [(2,0,-.5*(i-1),0) for i in range(1,12)]
COMMANDS += [(0,2,0,(i-14)*.1875) for i in range(12,17)]
COMMANDS += [(3 if a else 0,3 if f else 0,a,f)
             for a in (.125,.03125,0,-.03125,-.125) for f in (.03125,0,-.03125)]

def am7(i):
    if i==0:return -8.0
    if i<16:return .25*i-7.75
    if i<32:return .0625*i-4.9375
    return .03125*i-3.96875

def fm7(i):return i/32-2

def apply(action,offset,current,default,low,high):
    if action==0:return current
    if action==1:return default
    if action==2:return offset
    return None if current is None else max(low,min(high,current+offset))

class Decoder:
    def __init__(self):self.state=[-8.0,0.0,-8.0,0.0] # low am/fm, high am/fm
    def invalidate(self):self.state=[None]*4
    def command(self,band,code):
        a,f,da,df=COMMANDS[code];i=2*band
        self.state[i]=apply(a,da,self.state[i],-8,-8,0)
        self.state[i+1]=apply(f,df,self.state[i+1],0,-2,2)
    def pair(self,hi,lo):self.command(1,hi);self.command(0,lo)
    def output(self):
        def convert(v,center):
            if v is None:return None
            return (0.0 if v < -7.9375 else 2.0**v)*center
        values=[convert(v,c) for v,c in zip(self.state,(1,160,1,320))]
        return dict(zip(('low_amplitude','low_hz','high_amplitude','high_hz'),values),state_complete=all(v is not None for v in self.state))
    def decode(self,data):
        if len(data)!=4:raise ValueError('One motor word must be four bytes')
        w=int.from_bytes(data,'little');kind=w>>30
        def field(offset,width):return (w>>offset)&((1<<width)-1)
        samples=[]
        if kind==0:return dict(format='no_new_samples',samples=[])
        if kind==1 and field(0,20)==0:
            fmt='one_5bit';self.pair(field(20,5),field(25,5));samples.append(self.output())
        elif kind==1 and field(0,2)==0:
            fmt='one_7bit'
            self.state=[am7(field(23,7)),fm7(field(16,7)),am7(field(9,7)),fm7(field(2,7))]
            samples.append(self.output())
        elif kind==1:
            fmt='three_7bit';band=field(0,1);component=field(2,1)
            self.state[2*band+component]=(fm7 if component else am7)(field(23,7))
            samples.append(self.output())
            self.pair(field(13,5),field(18,5));samples.append(self.output())
            self.pair(field(3,5),field(8,5));samples.append(self.output())
        elif kind==2 and field(0,10)==0:
            fmt='two_5bit'
            for hi,lo in ((20,25),(10,15)):
                self.pair(field(hi,5),field(lo,5));samples.append(self.output())
        elif kind==2:
            fmt='two_7bit';band=field(0,1)
            self.state[2*band]=am7(field(23,7));self.state[2*band+1]=fm7(field(1,7))
            self.command(1-band,field(18,5));samples.append(self.output())
            self.pair(field(8,5),field(13,5));samples.append(self.output())
        else:
            fmt='three_5bit'
            for hi,lo in ((20,25),(10,15),(0,5)):
                self.pair(field(hi,5),field(lo,5));samples.append(self.output())
        return dict(format=fmt,samples=samples)

def decode_capture(path):
    log=json.loads(path.read_text(encoding='utf-8-sig'))['newest'];left=Decoder();right=Decoder();rows=[]
    continuous=log['version']==5
    for index,event in enumerate(log['events']):
        if not continuous and index==log['first_count'] and log['dropped_middle_events']:
            left.invalidate();right.invalidate()
        if continuous:
            if event['motors_hex'] is None:continue
            motors=bytes.fromhex(event['motors_hex'])
        else:
            raw=bytes.fromhex(event['raw_hex'])
            if raw[0] not in (1,0x10) or len(raw)<10:continue
            motors=raw[2:10]
        rows.append(dict(at_ms=event['at_ms'],at_us=event.get('at_us'),report_id=event['report_id'],
            left=left.decode(motors[:4]),right=right.decode(motors[4:])))
    return dict(source=path.name,offline_only=True,hardware_output=False,
        complete=log['complete'] if continuous else not log['dropped_middle_events'],
        dropped_events=log['dropped_events'] if continuous else log['dropped_middle_events'],
        note='Continuous logs retain the prefix on overflow; truncated logs are not complete. Old first/tail logs invalidate state at the gap. Samples are protocol values, not measured actuator amplitude.',events=rows)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('capture',type=pathlib.Path);p.add_argument('--output',type=pathlib.Path,required=True)
    a=p.parse_args();a.output.write_text(json.dumps(decode_capture(a.capture),indent=2),encoding='utf-8')
    print(str(a.output))
