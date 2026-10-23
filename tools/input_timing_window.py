"""Read-only local timing prompts; no controller, socket, or arming command."""
import json,math,pathlib,sys,time
from input_timing import view

def main(path):
    import tkinter as tk
    root=tk.Tk();root.title('120秒按键复测：震动输出关闭');root.geometry('610x280');root.attributes('-topmost',True)
    title=tk.Label(root,text='等待主机输入链路连接……',font=('Microsoft YaHei UI',16),wraplength=570);title.pack(pady=25)
    detail=tk.Label(root,text='出现手柄图标后，用飞智进入按键检查页。\n等待本窗口提示，再短按下方B、右方A并松开。',font=('Microsoft YaHei UI',11),wraplength=570);detail.pack(pady=12)
    tk.Label(root,text='本窗口只提示时间，不启用震动，也不会代替你按键。').pack(pady=8)
    beeped=set()
    def poll():
        try:data=json.loads(path.read_text(encoding='utf-8'))
        except (OSError,ValueError):data={}
        state,remaining=view(data,time.monotonic());seconds=math.ceil(remaining)
        if state=='ENDED':
            title.configure(text='本轮已结束，请等待收尾。',fg='black');detail.configure(text='按此前步骤，接入满190秒后按住BOOTSEL接回电脑。');root.after(4000,root.destroy);return
        if state in ('EARLY_PRESS','LATE_PRESS'):
            title.configure(text=f'现在依次短按 B、A，然后松开（{seconds}秒）',fg='green')
            detail.configure(text='请看 Switch 2 检查页是否分别显示 B、A。')
            if state not in beeped:beeped.add(state);root.bell()
        elif state=='RELEASE':title.configure(text=f'全部松开，摇杆居中；剩余约{seconds}秒',fg='black')
        elif state in ('EARLY_COUNTDOWN','LATE_COUNTDOWN'):
            title.configure(text=f'距第{1 if state=="EARLY_COUNTDOWN" else 2}次按键提示：{seconds}秒',fg='black')
            detail.configure(text='先进入按键检查页，等待绿色提示；不要凭接入时间估计。')
        root.after(150,poll)
    root.after(100,poll);root.mainloop()

if __name__=='__main__':main(pathlib.Path(sys.argv[1]))
