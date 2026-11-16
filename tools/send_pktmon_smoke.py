"""Three non-controller CLK1 UDP broadcasts; no Pico, HID or firmware commands."""
import argparse,json,pathlib,re,socket,struct,time
from capture_clock import precise_utc_reader,anchor
ROOT=pathlib.Path(__file__).absolute().parents[1]

def main():
    p=argparse.ArgumentParser();p.add_argument('--run-id',required=True);a=p.parse_args()
    if not re.fullmatch(r'\d{8}-\d{6}',a.run_id):p.error('Invalid run identifier')
    folder=ROOT/'handoff/2026-10-22/work/private'/('pktmon-smoke-'+a.run_id)
    out=folder/'sender.json'
    if not folder.is_dir() or out.exists():raise ValueError('Expected fresh helper-owned directory')
    utc=precise_utc_reader();anchors=[anchor(utc)];sent=[]
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET,socket.SO_BROADCAST,1);sock.bind(('192.168.137.1',0))
        for sequence in range(3):
            payload=b'CLK1'+struct.pack('<I',sequence)+a.run_id.encode('ascii')
            begin=time.perf_counter();size=sock.sendto(payload,('192.168.137.255',49724));end=time.perf_counter()
            sent.append(dict(sequence=sequence,begin_perf=begin,end_perf=end,bytes=size));time.sleep(.25)
    anchors.append(anchor(utc))
    with out.open('x',encoding='utf-8') as f:json.dump(dict(kind='three_non_controller_CLK1_packets',anchors=anchors,sent=sent,motor_commands=0,pico_access=False),f,indent=2)
    return 0
if __name__=='__main__':raise SystemExit(main())
