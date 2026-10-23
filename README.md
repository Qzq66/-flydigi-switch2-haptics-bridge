# 八爪鱼 6 Pro → Switch 2 触觉桥接

目标：在 Switch 2 真机游戏中使用飞智八爪鱼 6 Pro，并转换主机触觉输出。

**2026-10-23：离线《空之轨迹2nd》摇杆进门场景，飞智输入与受限震动提示闭环已连续两轮独立通过。两轮分别581/581、563/563字段一致，启用前零输出、左右各一次完整120ms/±12提示、结束握手与配置核对通过，用户确认进门短震动及无残留。此为提示映射，原生HD Rumble 2保真、长期稳定性和独立硬件运行仍未验证。**

## 接续入口

- [最新跨机接续：2026-10-23 GitHub同步](docs/GITHUB_RESUME_2026-10-23.md)
- [受限游戏提示成功基线与恢复说明](docs/STAGED_GAME_BASELINE_2026-10-23.md)
- [游戏验证过程、失败反例与两轮成功证据](docs/WINDOWS_GAME_PILOT_2026-10-23.md)
- [历史：Windows接续Mac五项工作](docs/WINDOWS_RESUME_2026-10-22.md)

- [Mac 离线进展：九组142项与收尾修正](docs/MAC_OFFLINE_RESULTS_2026-10-22.md)（尚无硬件复测）
- [Windows → macOS 详细交接](docs/HANDOFF_2026-10-22.md)
- [Mac 拉取、离线检查、构建及移植清单](docs/MAC_CONTINUE_2026-10-22.md)
- [当前状态与验收](docs/STATUS.md)
- [已实现协议、结束确认和保护](docs/PROTOCOL_NOTES_2026-10-22.md)
- [源码/证据快照](handoff/2026-10-22/)
- [最新暂停交接原记录](handoff/2026-10-22/outputs/游戏短测暂停交接.md)

快照保留相对目录结构，包含Windows原型、纯解码与离线测试、v035/v040/v042固件源码和筛选证据。**Windows硬件脚本尚未移植到Mac**；不要直接运行硬件入口。可先执行：

```sh
python3 tools/run_offline_checks.py
```

v042 RAM与实际参数Flash均已验证；输入、末帧/持久END2确认、故障停止和显式启用的游戏短提示已完成Windows硬件复测。游戏内连接需飞智L+R、再A确认，正式震动测试另由电脑按钮启用。一次60秒窗口的成功不代表持续游戏或所有场景适配。

## 硬件与状态

- 第三方创客版Pico2W，RP2350，实测4MiB Flash；标准pico2_w/CYW43路径已完成无线实测。
- Flydigi APEX6 Pro，接收器37D7:2502，设备类型96；Windows厂商HID FFA0/MI02，33B收发。
- 原厂手柄配置始终不保存、不重置、不升级；临时输出有独立监护与结束配置核对。
- 当前Pico在电脑BOOTSEL，保留v042测试程序与第10代日志；测试进程已退出。网络为iPhone USB供电脑、电脑2.4GHz热点供Pico。此次同步不启动硬件。

未上传热点密钥、会话令牌、原始Flash/手柄RAM备份、含密钥固件、私密基线压缩包、厂商DLL/EXE或本机工具链。脚本及报告中的Windows本地路径用于说明原环境，跨机须调整；烧写前必须私密取回原备份并重新核对。

## 历史资料

[开发计划](开发计划.md)、[旧Windows交接](docs/WINDOWS_HANDOFF.md)、[旧Mac实测](docs/MAC_RECEIVER_DIAGNOSIS.md)、[官方资料核对](docs/FLYDIGI_OFFICIAL_FINDINGS.md)、[跨平台约定](docs/CROSS_PLATFORM_WORKFLOW.md)保留作为历史背景。最新状态以STATUS及2026-10-23接续为准。第三方来源与许可证随快照保留。
