"""Read-only BPROLOG5 decoder. A complete log retains every valid motor field."""
import pathlib,struct,zlib,json,argparse
SLOT=65536;HEADER=128;RECORD=24;CAPACITY=(SLOT-HEADER-4)//RECORD
def decode_sector(data):
    if len(data)!=SLOT or data[:8]!=b'BPROLOG5':raise ValueError('length or magic')
    if zlib.crc32(data[:-4])!=struct.unpack_from('<I',data,SLOT-4)[0]:raise ValueError('CRC mismatch')
    version,generation,reason,elapsed,total=struct.unpack_from('<5I',data,8)
    stored,width=struct.unpack_from('<2H',data,28)
    flags,payload,target,capacity,first_drop,clock=struct.unpack_from('<6I',data,32)
    if version!=5 or reason not in (1,2,3,4) or flags&~7 or capacity!=CAPACITY or clock!=1000000:raise ValueError('header')
    if reason==3 and (total!=CAPACITY or flags&2):raise ValueError('invalid capacity termination')
    if reason==4 and (elapsed<180000 or flags&6 or total>=CAPACITY):raise ValueError('invalid boot-limit termination')
    if stored!=min(total,CAPACITY) or width!=RECORD or payload!=stored*RECORD:raise ValueError('counts')
    if target not in (0,0xe0000,0xf0000) or data[64:69]!=b'BCAP\x05':raise ValueError('identity or target')
    end_status=struct.unpack_from('<I',data,60)[0] if data[56:60]==b'END2' else None
    if end_status is not None and end_status not in (1,2):raise ValueError('invalid END2 status')
    overflow=total>stored
    if bool(flags&2)!=overflow or (first_drop!=0xffffffff)!=overflow:raise ValueError('overflow marker')
    if overflow and first_drop>elapsed*1000:raise ValueError('drop timestamp')
    events=[]
    for index in range(stored):
        r=data[HEADER+index*RECORD:HEADER+(index+1)*RECORD]
        at,seq=struct.unpack_from('<2I',r)
        rid,n,cmd,arg=r[8:12];ef=r[20]
        if seq!=index or n<1 or n>64 or ef&~3 or at>elapsed*1000:raise ValueError('record')
        has_motor=rid in (1,0x10) and n>=10
        redacted=rid==1 and n>=11 and cmd==1
        if bool(ef&1)!=has_motor or bool(ef&2)!=redacted or r[22:]!=b'\0\0':raise ValueError('record flags')
        events.append(dict(at_us=at,at_ms=at/1000,sequence=seq,report_id=f'{rid:02X}',wire_bytes=n,
            subcommand=f'{cmd:02X}' if rid==1 and n>=11 else None,first_argument=arg if n>=12 else None,
            packet_counter=r[21],pairing_arguments_redacted=redacted,
            motors_hex=r[12:20].hex() if has_motor else None))
    if any(a['at_us']>b['at_us'] for a,b in zip(events,events[1:])):raise ValueError('timestamp order')
    if overflow and events and first_drop<events[-1]['at_us']:raise ValueError('drop order')
    return dict(version=version,generation=generation,reason={1:'capture_deadline',2:'RAM_dry_run',3:'capacity_limit',4:'boot_limit'}[reason],
        elapsed_ms=elapsed,total_events=total,stored_events=stored,dropped_events=total-stored,capacity=capacity,
        overflow=overflow,complete=not overflow,first_dropped_at_us=first_drop if overflow else None,
        usb_mounted_seen=bool(flags&1),no_flash_marker=int(bool(flags&4)),target_offset=hex(target),
        crc_valid=True,diagnostics_raw_hex=data[64:128].hex(),events=events,
        stream_end=('client_confirmed' if end_status==1 else 'drain_timeout') if end_status is not None else None)
def decode_slots(data):
    if len(data) not in (SLOT,SLOT*2):raise ValueError('Expected one or two 64KiB slots')
    slots=[];valid=[]
    for offset in range(0,len(data),SLOT):
        try:
            record=decode_sector(data[offset:offset+SLOT]);record['slot_index']=offset//SLOT
            valid.append(record);slots.append(dict(slot_index=offset//SLOT,valid=True,generation=record['generation']))
        except ValueError as e:slots.append(dict(slot_index=offset//SLOT,valid=False,error=str(e)))
    if not valid:raise ValueError('No valid continuous capture')
    newest=valid[0]
    for item in valid[1:]:
        if 0<(item['generation']-newest['generation'])&0xffffffff<0x80000000:newest=item
    return dict(slots=slots,newest=newest)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('input',type=pathlib.Path);p.add_argument('--output',type=pathlib.Path,required=True)
    a=p.parse_args();result=decode_slots(a.input.read_bytes());a.output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result['newest'].items() if k!='events'},indent=2))
