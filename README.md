# 八爪鱼 6 Pro → Switch 2 触觉桥接

目标：在 Switch 2 真机游戏中使用飞智八爪鱼 6 Pro，并转换主机触觉输出。

**2026-10-22：真实主机的 USB → Pico → Wi-Fi → Windows → 飞智可感知提示已验证。120ms、样本偏移 ±12 时用户确认左右明显震动。完整游戏操控、原生 HD Rumble 2、高保真重建和独立硬件运行仍未验证。**

## 接续入口

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

v042在电脑RAM测试中已验证307/307事件、末帧/结束确认、按钮/摇杆转发与超时回中；未安装v042 Flash，完整游戏分支尚待验证。用户计划测试《空之轨迹2nd》，但原装手柄的震动场景尚未确认。

## 硬件与状态

- 第三方创客版Pico2W，RP2350，实测4MiB Flash；标准pico2_w/CYW43路径已完成无线实测。
- Flydigi APEX6 Pro，接收器37D7:2502，设备类型96；Windows厂商HID FFA0/MI02，33B收发。
- 原厂手柄配置始终不保存、不重置、不升级；临时输出有独立监护与结束配置核对。
- 交接时硬件测试已由用户暂停，Pico为原MicroPython、原热点已恢复。此次上传不恢复硬件测试。

未上传热点密钥、会话令牌、原始Flash/手柄RAM备份、含密钥固件、厂商DLL/EXE或本机工具链。公开副本中的序号/个人路径已脱敏，烧写前必须私密取回原备份并重新核对。

## 历史资料

[开发计划](开发计划.md)、[旧Windows交接](docs/WINDOWS_HANDOFF.md)、[旧Mac实测](docs/MAC_RECEIVER_DIAGNOSIS.md)、[官方资料核对](docs/FLYDIGI_OFFICIAL_FINDINGS.md)、[跨平台约定](docs/CROSS_PLATFORM_WORKFLOW.md)保留作为历史背景。最新实测状态以2026-10-22交接为准。第三方来源与许可证随快照保留。
