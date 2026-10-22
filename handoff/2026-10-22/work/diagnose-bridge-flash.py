"""Read only bridge diagnostics on exact Flash USB identity; never opens Flydigi."""
import pathlib,importlib.util,struct,socket,time,json,datetime
HERE=pathlib.Path(__file__).absolute().parent
spec=importlib.util.spec_from_file_location('probe',HERE/'test-pico-bridge-v040.py');p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p);m=p.m
report=dict(physical_output=False,flash_writes=0,snapshots=[])
try:
    m.lib.hid_init();deadline=time.perf_counter()+15
    while time.perf_counter()<deadline:
        head=m.lib.hid_enumerate(0x057e,0x2009);paths=[]
        try:
            node=head
            while node:
                d=node.contents
                if d.product_string=='Bridge Pro Live 040' and d.serial_number=='BPCAP-RP2350-LOCAL-040' and d.usage_page==1 and d.usage==4:paths.append(bytes(d.path))
                node=d.next
        finally:
            if head:m.lib.hid_free_enumeration(head)
        if paths:break
        time.sleep(.1)
    if len(paths)!=1:raise ValueError('Exact Flash USB not found')
    m.handle=m.lib.hid_open_path(paths[0]);m.allow_lr=True
    if m.read_virtual(0x9000,8)[:8]!=b'BCAP\5\0\0\0':raise ValueError('Flash diagnostic magic mismatch')
    m.verified=True
    until=time.perf_counter()+30
    while time.perf_counter()<until:
        d=m.read_range(0x9200,48)
        snap=dict(initialized=d[5],active=d[6],vibration=d[7],ip=socket.inet_ntoa(d[8:12]),link=struct.unpack_from('<i',d,36)[0],produced=struct.unpack_from('<I',d,12)[0])
        report['snapshots'].append(snap)
        if snap['ip'].startswith('192.168.137.'):
            from bridge_runtime import Client
            client=Client(snap['ip'],struct.unpack_from('<Q',d,40)[0])
            try:
                f=client.poll();report['udp_reply_received']=f is not None
                if f:report['udp_events']=len(f['events'])
            finally:client.close()
            break
        time.sleep(.5)
except BaseException as e:report['error']=repr(e)
finally:
    if m.handle:m.lib.hid_close(m.handle)
    m.lib.hid_exit()
    path=HERE.parent/'outputs'/('bridge-flash-diagnostic-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'.json')
    path.write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2));print(str(path))
