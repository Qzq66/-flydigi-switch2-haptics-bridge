# 有界组件捕获助手与三包时钟小样本

已实现独立捕获助手、原始字节命令记录、PCAPNG/IPv4 UDP解析器、UTC/进程内性能时钟锚点和小样本分析器。[24项Python离线检查](PKTMON_CAPTURE_OFFLINE_2026-10-25.json)及[8项PowerShell归属/语法检查](PKTMON_CAPTURE_GUARDS_2026-10-25.json)通过；ValidateOnly模式没有访问驱动或改变过滤器。旧9文件只读清单冻结证据不改。

助手执行前重新确认管理员令牌、没有PktMon捕获、没有过滤器及现有192.168.137.1/24热点地址。只添加唯一运行名的IPv4 UDP49724/主机地址过滤，使用有限16MB循环日志、所有组件点采集小样本。仅在确认当前日志属于本RunId时停止；清理过滤器前要求捕获已停止且列表只有本次过滤器。其他或未知状态保留，不清理他人诊断。原始命令输出和ETL/PCAPNG仅本机private，不公开原始地址、包体。

小样本由电脑发3个不属于桥接控制协议的CLK1广播包，间隔250ms，Pico保持BOOTSEL，不启动固件、访问手柄或发送马达命令。它验证工具链和输出格式，不复现Switch流量，也不证明无线延迟根因或完整接收路径。捕获预计数秒；各子命令/发送进程有超时及finally归属检查，停止仍依赖OS响应，未知外部会话不强行停止。

Microsoft的[PktMon语法说明](https://learn.microsoft.com/en-us/windows-server/networking/technologies/pktmon/pktmon-syntax)支持按实验流过滤及ETL转换；此处测量的是Windows组件观察点，不将其当物理无线到达时刻。[GetSystemTimePreciseAsFileTime](https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/nf-sysinfoapi-getsystemtimepreciseasfiletime)用于取得UTC，前后由本进程perf_counter夹住并记录实测区间；不跨进程直接比较Python3.9的性能时钟。两端锚点出现超过容差的漂移/不确定性则拒绝映射。

PCAPNG解析按[IETF工作草案](https://www.ietf.org/ietf-ftp/internet-drafts/draft-ietf-opsawg-pcapng-06.html)读取节字节序、接口时间分辨率/偏移、Enhanced Packet Block及方向/丢失提示；支持Ethernet/VLAN及原始IPv4，拒绝不支持的链路、分片、无时间戳块和损坏边界。保持section/interface身份，不把多组件副本计为网络重传。最初真实样本若格式不同，应保留原件、独立修订解析器，不改写原失败报告或补造时间戳。

## 实际三包小样本：20261025-212133

用户确认后已通过UAC执行。[捕获与清理报告](PKTMON_SMOKE_20261025-212133.json)记录捕获启动、停止、本次过滤器加入和移除均成功，清理错误为空；诊断发送器记录3次发送。没有访问Pico、发送马达命令或修改网络与手柄配置，Pico仍留电脑BOOTSEL，最后物理核验基准为31代。

[分析结果](PKTMON_SMOKE_ANALYSIS_20261025-212133.json)为 **INCOMPLETE**：未观察到任何实验数据包，不能进行捕获时间戳与发送时钟的实际对齐验证。[文件结构复核](PKTMON_SMOKE_STRUCTURE_20261025-212133.json)确认两个196字节PCAPNG各只有节头、接口及统计块，均无Enhanced Packet Block；不是已有包被当前UDP解析器漏读的证据。原始ETL为19519字节，统计仅3个事件；原始记录保留private。

当前只证明捕获生命周期及归属清理可以完成，尚未证明该广播发送路径可被捕获。热点无客户端等因素仍是假设，未确诊，不将发送成功当作捕获成功。未自动重发或启动第二次捕获。下一步先设计可明确验证的包路径，再单独安排受限捕获；不推进主机震动测试、不放宽80ms保护。新增材料仅本地保存，未上传GitHub。
