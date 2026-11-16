"""Independent same-process recovery timer. No device, network or capture access."""
import math

class RecoveryGate:
    def __init__(self,start,minimum_seconds=190):
        if not math.isfinite(start) or minimum_seconds<190:raise ValueError('At least190 seconds required')
        self.start=start;self.last=start;self.minimum=minimum_seconds
    def observe(self,now):
        if not math.isfinite(now) or now<self.last:raise ValueError('Recovery clock reversed')
        self.last=now;elapsed=now-self.start
        return dict(elapsed_seconds=elapsed,remaining_seconds=max(0.,self.minimum-elapsed),
            minimum_seconds=self.minimum,recovery_time_reached=elapsed>=self.minimum)

def main():
    import argparse,datetime,json,pathlib,time,tkinter as tk
    p=argparse.ArgumentParser();p.add_argument('--directory',type=pathlib.Path,required=True)
    p.add_argument('--connected-confirmed',action='store_true',required=True);a=p.parse_args()
    folder=a.directory.resolve()
    if not folder.is_dir() or 'private' not in folder.parts:raise ValueError('Existing private trial directory required')
    start=folder/'host-connected-clock.json';ready=folder/'recovery-time-reached.json'
    if start.exists() or ready.exists():raise ValueError('Preserve previous timing evidence')
    gate=RecoveryGate(time.perf_counter())
    with start.open('x',encoding='utf-8') as f:
        json.dump(dict(user_confirmed_connected=True,minimum_seconds=190,started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),motor_commands=0),f)
    root=tk.Tk();root.title('主机供电与日志回收计时');root.geometry('600x180');root.attributes('-topmost',True)
    label=tk.Label(root,text='',font=('Microsoft YaHei UI',13));label.pack(pady=35)
    def poll():
        state=gate.observe(time.perf_counter())
        if state['recovery_time_reached']:
            with ready.open('x',encoding='utf-8') as f:json.dump(state,f)
            label.configure(text='已满190秒。请等待明确提示后按BOOTSEL接回电脑。')
            return
        label.configure(text='请保持Pico接主机供电。\n距离日志回收至少还需：'+str(math.ceil(state['remaining_seconds']))+' 秒')
        root.after(250,poll)
    root.after(1,poll);root.mainloop()
    if not ready.exists():
        with (folder/'recovery-clock-cancelled.json').open('x',encoding='utf-8') as f:json.dump(dict(cancelled=True,recovery_allowed=False),f)
        return 1
    return 0

if __name__=='__main__':raise SystemExit(main())
