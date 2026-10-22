"""USB output injection -> Pico raw ring -> actual WiFi -> PC. No Flydigi output."""
import pathlib,importlib.util,time,json,ctypes as C,threading,datetime,socket,struct
from bridge_runtime import Client
here=pathlib.Path(__file__).absolute().parent
sp=importlib.util.spec_from_file_location('candidate',here/'test-pico-capture-v035-ram.py')
m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
report=dict(checks=[],status='INCOMPLETE',physical_output=False)
def check(name,ok):report['checks'].append(dict(name=name,passed=bool(ok)));assert ok,name
def find():
    until=time.monotonic()+20
    while time.monotonic()<until:
        head=m.lib.hid_enumerate(0xcafe,0x4012);matches=[]
        try:
            node=head
            while node:
                d=node.contents
                if d.product_string=='Bridge Pro Live 042' and d.serial_number=='BPCAP-RP2350-LOCAL-042' and d.usage_page==1 and d.usage==4:matches.append(bytes(d.path))
                node=d.next
        finally:
            if head:m.lib.hid_free_enumeration(head)
        if matches:return matches
        time.sleep(.1)
    return []
def open_candidate():
    m.lib.hid_init();matches=find();check('unique_candidate',len(matches)==1)
    m.handle=m.lib.hid_open_path(matches[0]);check('HID_open',bool(m.handle))
    check('RAM_identity',m.read_virtual(0x9000,8)==b'BCAP\5\0\0\1');m.verified=True;m.allow_lr=True
def endpoint():
    deadline=time.monotonic()+25
    while time.monotonic()<deadline:
        d=m.read_range(0x9200,48)
        if d[:4]!=b'BRD2':raise ValueError('Transport identity mismatch')
        if struct.unpack_from('<i',d,36)[0]==3 and d[8:11]==bytes([192,168,137]) and d[11] not in (0,1,255):
            value=dict(ip=socket.inet_ntoa(d[8:12]),session=f'{struct.unpack_from("<Q",d,40)[0]:016x}',port=49724)
            (here.parent/'outputs/bridge-v042-endpoint.json').write_text(json.dumps(value,indent=2),encoding='utf-8')
            return value
        time.sleep(.15)
    raise TimeoutError(f'WiFi join did not complete: link={struct.unpack_from("<i",d,36)[0]}, ip={socket.inet_ntoa(d[8:12])}')
def main():
    client=None;thread=None;stop=threading.Event();received=[];errors=[];rtts=[]
    try:
        open_candidate();ep=endpoint();report['endpoint']=ep
        discovery_spec=importlib.util.spec_from_file_location('live',here/'bridge-switch-live.py')
        discovery=importlib.util.module_from_spec(discovery_spec);discovery_spec.loader.exec_module(discovery)
        check('broadcast_discovery_exact_endpoint',discovery.discover(int(ep['session'],16),2)==ep['ip'])
        client=Client(ep['ip'],int(ep['session'],16))
        def collect():
            try:
                while not stop.is_set():
                    frame=client.poll()
                    if frame:
                        received.extend(frame['events']);rtts.append(frame['rtt_ms'])
                        if frame['flags']&16:client.confirm_end();return
                    time.sleep(.004)
            except BaseException as e:errors.append(repr(e))
        thread=threading.Thread(target=collect);thread.start()
        m.send(0x80,b'\4')
        check('input_mode',m.sub(3,b'\x30')[13]==0x80)
        check('IMU_mode2',m.sub(0x40,b'\2')[13]==0x80)
        check('vibration_enable',m.sub(0x48,b'\1')[13]==0x80)
        check('MCU_compat',m.sub(0x21,b'\x21')[13:15]==b'\x80\x21')
        check('SPI_write_rejected',m.sub(0x11,b'\0'*8)[13]==0)
        check('player_LED_zero',m.sub(0x30,b'\0')[13]==0x80)
        expected=[]
        for i in range(300):
            left=((1<<30)|((i%128)<<23)|(64<<16)|(64<<2)).to_bytes(4,'little')
            right=((1<<30)|((i%128)<<9)|(64<<16)|(64<<2)).to_bytes(4,'little')
            motors=left+right;expected.append(motors);m.send(0x10,bytes([i%16])+motors)
        deadline=time.monotonic()+3
        while time.monotonic()<deadline:
            produced=struct.unpack_from('<I',m.read_range(0x9200,24),12)[0]
            if len(received)>=produced:break
            time.sleep(.05)
        check('collector_no_errors',not errors)
        check('300_raw_words_exact',[e['motors'] for e in received][-300:]==expected)
        check('raw_sequence_contiguous',all(e['sequence']==i for i,e in enumerate(received)))
        check('raw_timestamps_monotonic',all(a['at_us']<=b['at_us'] for a,b in zip(received,received[1:])))
        check('no_transport_overflow',struct.unpack_from('<I',m.read_range(0x9200,24),20)[0]==0)
        # Radio polling and USB streaming must coexist with neutral Pro input.
        for _ in range(10):m.receive(0x30)
        check('USB_input_remains_responsive',True)
        time.sleep(1.2)
        stats=m.stats();check('single_registration_press_and_release',0<struct.unpack_from('<I',m.read_range(0x9034,4))[0]<40 and m.read_virtual(0x903c,1)[0]&7==7)
        def input_seen(expected,timeout=1.5):
            until=time.perf_counter()+timeout
            while time.perf_counter()<until:
                buf=C.create_string_buffer(64);n=m.lib.hid_read_timeout(m.handle,buf,64,30)
                if n<0:raise OSError('Pico input read failed')
                if n==64 and buf.raw[0]==0x30 and buf.raw[3:12]==expected:return True
            return False
        neutral=bytes.fromhex('000000000880000880')
        for name,state in [('face_bottom',bytes.fromhex('040000000880000880')),('shoulders',bytes.fromhex('c000c0000880000880')),('full_axes',bytes.fromhex('000000c001e4c001e4'))]:
            client.input_source=lambda state=state:state
            check('relay_'+name,input_seen(state))
        client.input_source=None
        check('input_timeout_returns_to_neutral',input_seen(neutral))
        invalid=bytes.fromhex('001000000880000880')
        client.input_source=lambda:invalid
        time.sleep(.12)
        check('home_injection_rejected',input_seen(neutral))
        client.input_source=None
        time.sleep(.12)
        produced=struct.unpack_from('<I',m.read_range(0x9200,24),12)[0]
        m.send(0x10,b'\0'+bytes.fromhex('0001404000014040'))
        m.send(0x80,b'\xfcENDLAB42')
        deadline=time.perf_counter()+3
        while time.perf_counter()<deadline and thread.is_alive():time.sleep(.01)
        check('explicit_stream_end_received',client.terminal_received)
        check('last_neutral_field_received',received[-1]['motors']==bytes.fromhex('0001404000014040'))
        check('final_event_count_exact',len(received)==produced+1)
        check('final_sequence_exact',received[-1]['sequence']==produced)
        check('collector_completed_without_errors',not errors and not thread.is_alive())
        check('end_acknowledgement_replied',client.terminal_ack_replied)
        report['terminal_ack_replied']=client.terminal_ack_replied
        report.update(status='PASSED_USB_WIFI_RAW_INTEGRATION',events=len(received),duplicates=client.duplicates,final_usb_stats=stats,rtt_ms=rtts)
    except BaseException as e:report['error']=repr(e)
    finally:
        stop.set()
        if thread:thread.join(timeout=1)
        if client:client.close()
        if m.handle:
            if m.verified and not (client and client.terminal_received):
                try:m.send(0x80,b'\xfeRESETLAB')
                except BaseException as e:report['reboot_error']=repr(e)
            m.lib.hid_close(m.handle)
        m.lib.hid_exit()
        report['collector_errors']=errors
        path=here.parent/'outputs'/('pico-bridge-v042-raw-test-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'.json')
        path.write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps({k:v for k,v in report.items() if k!='rtt_ms'},indent=2));print(str(path))
    return 0 if report['status']=='PASSED_USB_WIFI_RAW_INTEGRATION' else 1
if __name__=='__main__':raise SystemExit(main())
