"""Unified manual desktop launcher. Import/status helpers never open devices."""
import json,pathlib,re,sys,os,queue,threading,subprocess
ROOT=pathlib.Path(__file__).absolute().parents[1];PRIVATE=ROOT/'handoff/2026-10-22/work/private'
PLAN=ROOT/'docs/STARTUP_GAME_G60_PLAN_2026-11-15.json'
def cancel_path(stamp):
    if not re.fullmatch(r'\d{8}-\d{6}',stamp):raise ValueError('Invalid session stamp')
    return PRIVATE/('fidelity-game-arm-'+stamp+'.cancel')
def main():
    import tkinter as tk
    root=tk.Tk();root.title('飞智桥接：三事件会话');root.geometry('760x410')
    state=dict(proc=None,stamp=None,cancel=False);events=queue.Queue()
    label=tk.Label(root,text='Pico先留电脑BOOTSEL。先网页自测按键、退出Steam。\n本入口仅三事件，不是无限连续游戏。',wraplength=710,font=('Microsoft YaHei UI',12));label.pack(pady=25)
    progress=tk.Label(root,text='等待开始；输出仍需后续单独手动启用。',wraplength=700);progress.pack(pady=12)
    def request_stop():
        state['cancel']=True
        if state['stamp']:cancel_path(state['stamp']).write_text('cancel',encoding='ascii')
        progress.configure(text='已请求停止，等待原程序确认关闭和配置核对；不要插拔接收器。')
    def read_output(proc):
        for line in proc.stdout:events.put(('line',line.strip()))
        events.put(('ended',proc.wait()))
    def start():
        if state['proc'] is not None and state['proc'].poll() is None:return
        if not PLAN.exists():label.configure(text='候选计划未准备完成，未启动任何设备。');return
        state.update(stamp=None,cancel=False)
        pic=ROOT.parent/'pico-work-20261022/picotool-2.3.1/picotool/picotool.exe'
        proc=subprocess.Popen([sys.executable,'-B',str(ROOT/'tools/run_startup_game_g60.py'),'--play',str(PLAN),'--picotool',str(pic)],cwd=str(ROOT),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',env=dict(os.environ,PYTHONIOENCODING='utf-8'),creationflags=subprocess.CREATE_NO_WINDOW)
        state['proc']=proc;button.configure(state='disabled');label.configure(text='正在核对Flash和网络。Pico保持电脑BOOTSEL。');threading.Thread(target=read_output,args=(proc,),daemon=True).start()
    button=tk.Button(root,text='开始本轮预检',command=start);button.pack(pady=10)
    tk.Button(root,text='请求停止并安全收尾',command=request_stop).pack(pady=10)
    def poll():
        while not events.empty():
            kind,value=events.get_nowait()
            if kind=='ended':
                button.configure(state='normal');label.configure(text='程序侧已通过，仍须BOOTSEL回收日志。' if value==0 else '本轮未通过或已取消。保留日志，未自动重试。');progress.configure(text='请勿直接重复启动；Flash日志更新后需核验当前基准。');continue
            if value.startswith('SESSION_STAMP:'):
                stamp=value.split(':',1)[1];cancel_path(stamp);state['stamp']=stamp
                if state['cancel']:request_stop()
            elif 'PC_INPUT_LIVENESS_REQUIRED' in value:label.configure(text='请在按键窗口点开始，按提示完成A、松开、B、松开；Pico仍留电脑。')
            elif 'FIDELITY_GAME_DISCOVERY_READY' in value:label.configure(text='监听就绪：现在拔Pico，不按BOOTSEL经CM473接离线主机。\n完成登记再回游戏，全松后点另一个窗口的震动启用。')
        stamp=state['stamp'];proc=state['proc']
        if stamp and proc is not None and proc.poll() is None and not state['cancel']:
            try:
                data=json.loads((PRIVATE/('fidelity-game-phase-'+stamp+'.json')).read_text());phase=data.get('phase')
                if phase=='ARMED':progress.configure(text=f'已启用：完成{data.get("completed_events",0)}/3，剩余{data.get("armed_seconds_left",15):.1f}秒；每次停止后等至少1秒。')
                elif phase=='MUTED':progress.configure(text='三事件窗口已停止，不会重播；轻推摇杆核对操控，再全松。')
                elif phase=='MUTED_FAULT':progress.configure(text='保护已触发，输出锁定，不会自动恢复。等待收尾。')
                elif phase=='WAITING_SOURCE':progress.configure(text='\u7b49\u5f85\u4e3b\u673a\u9707\u52a8\u6e90\u5c31\u7eea\uff0c\u5e76\u8fde\u7eed\u5b89\u9759500\u6beb\u79d2\uff1b\u5c1a\u672a\u542f\u7528\u9707\u52a8\u3002')
                elif phase=='INPUT_READY':progress.configure(text='仅转发按键，未启用震动。先完成游戏内L+R/A，再全松手动启用。')
            except (OSError,ValueError):pass
        root.after(150,poll)
    def close():
        if state['proc'] is not None and state['proc'].poll() is None:request_stop();return
        root.destroy()
    root.protocol('WM_DELETE_WINDOW',close);root.after(150,poll);root.mainloop()
if __name__=='__main__':main()
