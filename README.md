# 八爪鱼 6 Pro → Switch 2 触觉桥接

目标：在 Switch 2 真机游戏中使用飞智八爪鱼 6 Pro，并转换主机触觉输出。

**2026-10-24：v043已通过120秒输入验收及两轮独立120秒离线游戏闭环。第14代1107/1107、第15代1120/1120字段一致，每轮25项组合验收通过；启用前零输出、左右各一次120ms/±12提示、结束握手和原厂配置一致，用户两次确认进门震动及无残留。此为受限提示映射，原始HD Rumble 2保真、长期稳定性及独立硬件运行仍未验证。旧v042的60秒两轮成功保留为历史基线。**

## 接续入口

- [最新跨机接续与本次公开同步：2026-10-24](docs/GITHUB_RESUME_2026-10-24.md)
- [v043本地固化、恢复与Windows/macOS入口](docs/V043_RESUME_2026-10-24.md)
- [v043两轮120秒证据总览](docs/V043_TWO_GAME_TRIALS.md)
- [v043冻结哈希清单（私密档案不公开）](docs/V043_BASELINE_2026-10-24.json)

- [Mac最新进度重读与资料收集（2026-10-23）](docs/MAC_PROGRESS_REVIEW_2026-10-23.md)

- [历史：2026-10-23 v042 GitHub同步](docs/GITHUB_RESUME_2026-10-23.md)
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

快照保留相对目录结构，包含Windows原型、纯解码与离线测试、v035/v040/v042/v043固件源码和筛选证据。**Windows硬件脚本尚未完整移植到Mac**；不要直接运行硬件入口。可先执行（如报告已存在，请换新文件名）：

```sh
python3 tools/run_offline_checks.py --report docs/MAC_V043_OFFLINE_LOCAL.json
```

v043 RAM持续运行/容量边界、实际参数Flash、120秒输入与两轮手动启用游戏提示已验证；v042旧基线保留。游戏内连接需飞智L+R、再A确认，正式震动测试另由电脑按钮启用。120秒live、180秒启动上限、日志满安全收尾、80ms断流与原提示预算均受保护；两轮同场景不代表长期持续游戏或所有场景适配。

## 硬件与状态

- 第三方创客版Pico2W，RP2350，实测4MiB Flash；标准pico2_w/CYW43路径已完成无线实测。
- Flydigi APEX6 Pro，接收器37D7:2502，设备类型96；Windows厂商HID FFA0/MI02，33B收发。
- 原厂手柄配置始终不保存、不重置、不升级；临时输出有独立监护与结束配置核对。
- 最近硬件收尾状态为Pico电脑BOOTSEL，保留v043程序与第15代日志，测试进程已退出；本次同步不重新读取设备。网络为iPhone USB供电脑、电脑2.4GHz热点供Pico，跨机仍须核对实际连接状态。

未上传热点密钥、会话令牌、原始Flash/手柄RAM备份、含密钥固件、私密基线压缩包、厂商DLL/EXE或本机工具链。脚本及报告中的Windows本地路径用于说明原环境，跨机须调整；烧写前必须私密取回原备份并重新核对。

## 历史资料

[开发计划](开发计划.md)、[旧Windows交接](docs/WINDOWS_HANDOFF.md)、[旧Mac实测](docs/MAC_RECEIVER_DIAGNOSIS.md)、[官方资料核对](docs/FLYDIGI_OFFICIAL_FINDINGS.md)、[跨平台约定](docs/CROSS_PLATFORM_WORKFLOW.md)保留作为历史背景。最新状态以STATUS及2026-10-24接续为准。第三方来源与许可证随快照保留。
