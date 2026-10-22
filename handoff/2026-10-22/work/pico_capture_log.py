"""Read-only decoder for BPROLOG3 (two 4KiB slots); never opens USB devices."""
import argparse
import json
import pathlib
import struct
import zlib

SECTOR=4096
EVENT=72

def decode_sector(data):
    if len(data)!=SECTOR:raise ValueError('sector length')
    if data[:8]!=b'BPROLOG3':raise ValueError('magic')
    if zlib.crc32(data[:4092])!=struct.unpack_from('<I',data,4092)[0]:raise ValueError('CRC mismatch / partial write')
    version,generation,reason,elapsed,total=struct.unpack_from('<5I',data,8)
    first,last=struct.unpack_from('<2H',data,28)
    flags,payload,target=struct.unpack_from('<3I',data,32)
    if version!=3 or reason not in (1,2) or first>24 or last>24 or flags&~1:raise ValueError('header fields')
    if first!=min(total,24) or last!=min(max(total-24,0),24) or payload!=(first+last)*EVENT:raise ValueError('event counts')
    if target not in (0,0xf0000,0xf1000):raise ValueError('target')
    if data[64:68]!=b'BCAP' or data[68]!=3:raise ValueError('firmware marker')
    events=[]
    for i in range(first+last):
        record=data[128+i*EVENT:128+(i+1)*EVENT]
        at=struct.unpack_from('<I',record)[0];n=record[4];eflags=record[5]
        if not 1<=n<=64 or eflags&~1 or at>elapsed:raise ValueError('event boundary')
        raw=record[8:8+n]
        events.append(dict(at_ms=at,wire_bytes=n,report_id=f'{raw[0]:02X}',
                           subcommand=f'{raw[10]:02X}' if raw[0]==1 and len(raw)>=11 else None,
                           pairing_arguments_redacted=bool(eflags&1),raw_hex=raw.hex()))
    if any(events[i]['at_ms']>events[i+1]['at_ms'] for i in range(len(events)-1)):raise ValueError('event order')
    return dict(version=version,generation=generation,reason='capture_deadline' if reason==1 else 'RAM_dry_run',
                elapsed_ms=elapsed,total_events=total,first_count=first,tail_count=last,
                dropped_middle_events=max(total-first-last,0),usb_mounted_seen=bool(flags&1),
                target_offset=hex(target),crc_valid=True,no_flash_marker=data[71],
                diagnostics_raw_hex=data[64:128].hex(),events=events)

def decode_slots(data):
    if len(data) not in (SECTOR,2*SECTOR):raise ValueError('Expected one or two sectors')
    slots=[];valid=[]
    for offset in range(0,len(data),SECTOR):
        try:
            record=decode_sector(data[offset:offset+SECTOR]);record['slot_index']=offset//SECTOR
            valid.append(record);slots.append(dict(slot_index=offset//SECTOR,valid=True,generation=record['generation']))
        except ValueError as exc:slots.append(dict(slot_index=offset//SECTOR,valid=False,error=str(exc)))
    if not valid:raise ValueError('No complete valid capture in provided bytes')
    newest=valid[0]
    for item in valid[1:]:
        delta=(item['generation']-newest['generation'])&0xffffffff
        if delta and delta<0x80000000:newest=item
    return dict(slots=slots,newest=newest)

def main():
    p=argparse.ArgumentParser();p.add_argument('input',type=pathlib.Path);p.add_argument('--output',type=pathlib.Path)
    a=p.parse_args();result=decode_slots(a.input.read_bytes())
    text=json.dumps(result,indent=2,ensure_ascii=False)
    if a.output:a.output.write_text(text,encoding='utf-8')
    print(text)

if __name__=='__main__':main()
