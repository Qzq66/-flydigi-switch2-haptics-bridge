> 2026-10-22 接续更新：此文保留为早期记录。当前实测、用户不改原厂配置的约束和 Mac 待移植事项，以 [最新交接](HANDOFF_2026-10-22.md) 与 [Mac 接续指南](MAC_CONTINUE_2026-10-22.md) 为准；不要直接照旧文开启持久接管设置。

# Mac 接收器诊断记录

日期：2026-10-21

## 实机条件

用户确认手柄开机，使用原装 2.4 GHz 接收器，当前模式为 XInput。

## 已验证

- macOS 枚举到 Flydigi APEX 6，VID:PID 为 `37d7:2502`，USB Full Speed 12 Mbps。
- 接口 0 为厂商类 XInput 接口（class/subclass/protocol 为 `ff/5d/01`），当前未匹配游戏输入驱动。
- 厂商 HID collection 为 `ffee` 和 `ffa0`，另有键盘 collection。
- 用户授予输入读取权限并重启应用后，IOHIDManager 与两个厂商 collection 均可非独占打开，返回成功。
- 被动监听厂商 collection 20 秒收到 0 个报告；不能由此判断无线未配对或手柄故障。
- 向 `ffa0` 发送 32 字节、report ID 0 的设备身份查询 `5a a5 01 02 00` 和状态查询 `5a a5 10`（余字节补零），两次发送均成功并得到 32 字节回复。
- 身份回复以 `5a a5 01 01 00 96` 开头，设备类型字段 `0x96=150`，对应 APEX 6 Pro。
- 状态回复以 `5a a5 10 01 00 00 00 00 00 00` 开头，偏移 9 的值为 0。

## 解释与边界

SDL 的 Flydigi V2 驱动将状态回复 `data[9] == 1` 判断为允许第三方接管；否则提示在飞智空间站开启 Allow third-party apps to take over mappings。当前设备报告值为 0，符合未允许接管的情况。这是厂商输入流不可用的重要线索，不能据此保证开启后所有 macOS 游戏均兼容。

输入监控权限与手柄端接管开关是两回事。USB 枚举、查询回复、厂商输入流、系统标准手柄识别和原生音圈反馈也应分别验证。

本次未发送 acquire/takeover、设置写入、固件更新、马达或震动命令。没有验证实际按键包、无线输入链路、游戏兼容或震动能力。

## 下一步

优先在 Windows 飞智空间站检查并启用第三方应用接管映射相关选项，记录实际选项名称及固件版本。回 Mac 后复查状态值，再使用有释放逻辑的临时接管实验读取厂商输入。不要默认临时接管等于 macOS 原生手柄支持。

## 探测程序

`tools/macos_hid_probe.swift`：只匹配上述 VID/PID 的厂商 collection；默认被动监听。`--query` 仅追加身份与状态查询。无配置持久化或震动写入。

参考：https://github.com/libsdl-org/SDL/blob/main/src/joystick/hidapi/SDL_hidapi_flydigi.c （HIDAPI_DriverFlydigi_HandleStatusResponse）
