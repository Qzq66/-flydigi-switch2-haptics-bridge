> 历史阶段记录；当前状态以仓库 docs/HANDOFF_2026-10-22.md 和 docs/STATUS.md 为准。路径及设备序号已脱敏。

# 飞智 Engine 扫描与桥接价值分析

日期：2026-10-21（中国时间）。扫描对象：本机 D:\Engine 安装文件及 Flydigi 用户目录中的配置、日志。仅作读取和静态字符串分析；未启动升级工具、修改配置或向手柄发送命令。

## 核心结论

发现了可继续研究的 Windows HID 输出路径和诊断入口，但尚未取得真实波形输出包，也未完成左右独立波形或停止测试。当前最有价值的工作是读取 Engine 的运行诊断，取得实际帧和采样参数，再与已公开的协议实现交叉验证。

## 已有证据

| 发现 | 证据和含义 | 限制 |
| --- | --- | --- |
| xHaptics Engine 5.0.2.6 | 卸载注册项、EXE 字符串、release-manifest 一致；安装目录 D:\Engine | 版本只描述本次安装 |
| Engine 曾识别到八爪鱼 | 2026-10-21 日志 device.connected：Flydigi APEX 6，deviceCode=k6，VID=37D7，PID=2502 | 是历史连接记录；名称未包含 Pro，不能单凭它判定所有子型号或固件 |
| Windows HID 输出路径存在 | EXE 引用 CreateFileW、WriteFile、HidP_GetCaps、HidD_GetAttributes，包含 HID 读写失败和 ACK 超时信息 | 未还原实际调用参数和报文 |
| 私有报告负载上限线索 | 字符串：HID frame exceeds 32 byte private report payload；另有 referenceReportLen=33、privateReportPayloadLen=32 | 33 字节可能包含报告 ID，仍需真实帧核对；不能称为已解析波形格式 |
| 查询命令线索 | 0x01 GetDeviceInfo；0x04 GetDeviceUuid | 来自错误消息，尚无请求与响应样本 |
| 马达映射命令线索 | 0xA3 motor mapping response；预期响应长度 64 字节，且检查 active slot | 是映射读取线索，不能直接视为 PCM 波形发送命令 |
| 音频输入要求线索 | X-Haptics requires 48000 Hz PCM；process-loopback 48000Hz 2ch float | 这是音频处理输入要求，不是马达输出采样率，更不代表 USB Audio 传输 |
| 发送诊断字段存在 | lastFrameHex、lastFrameBytes、lastMotorConfigFrameHex、motorConfigWrites、framesSent、writeFailures、inputReportLength | 字段的实际值尚未读到，帧截取长度也待检查 |
| 波形监控字段存在 | audioSampleRateHz、motorSampleRateHz、motorRateHz、audioIn、triggerOut、gripOut；diagnostics.wave.snapshot | 未获得运行样本，输出率未知；还需核查左右通道布局 |

EXE SHA-256：2B0FAE2A74C0C66445D1E2C36E2460CA9523D3BD583FC8B41F6E626B7B189A0C。

## 可用的本地接口线索

安装包自带 ui/diagnostics 页面，其 JavaScript 明确读取 /api/diagnostics/runtime-inspection，并通过 WebSocket 接收诊断事件。EXE 中也存在以下路径：

- /api/engine/version
- /api/engine/xhaptics/readiness
- /api/diagnostics/runtime-inspection
- /api/xhaptics/status
- /api/engine/status/stream
- /api/engine/ws-ticket
- /api/v1/xhaptics/device-target
- /api/v1/xhaptics/output-policy
- /api/device/controller/owner/acquire、renew、release

这些路径只是代码中的存在证据，完整方法、参数、权限及返回结构尚未验证。当前扫描未成功获取运行时 HTTP 响应。扫描环境中的进程与监听端口查询未给出 Engine 条目；CIM 查询被环境拒绝，不能据此断言用户桌面上的 Engine 未运行。USB 注册表里有历史枚举，也不能当作当前在线设备证据。

诊断前端使用 gpa6.v1 WebSocket 子协议，并通过 ws-ticket 申请票据；还存在 bearer、UI token 和启动令牌机制。应沿现有客户端流程接入，不通过打印或保存凭据进行分析。协议警告日志的 expectedProtocolVersion=1、versionProvided=false；后续客户端需核对 X-Protocol-Version 请求头。不能把 HTTP 路径猜测失败当作设备协议失败。

## 配置和日志的实际观察

- 当前用户 global.json 中 config.enabled=false。它表示所存全局配置的开关状态，不能独立代表当前全部运行会话。
- motor_output.json 含 triggerMixStartPct=10、triggerMixFullPct=25、triggerMixCurve=1、triggerGripMinimumPct=50。这些是混合策略参数，未发现可直接据此生成 HID 包的定义。
- racing_telemetry.json 指向 127.0.0.1:5300；结合程序中的 UDP 接收器线索，这是遥测候选入口，不能当作原始左右 PCM 注入接口或 HTTP 端口。
- 最新日志文件包含两次设备连接、两次断连、39 次缺少协议版本警告、31 次路由未找到，以及屏幕上传超时。屏幕上传属于另一功能，不能用其成败推断触觉链路。
- 未发现本次可确认的触觉帧发送成功、左右独立波形、固定频率或断流停止的验收记录。
- 程序保留 WebHID 与 Engine 之间的设备占用交接、暂停恢复及马达映射恢复路径。后续自写输出实验应先确认设备占用，避免与 Engine 同时争用同一接口。

## 对 Switch 2 桥接项目的直接价值

1. 以 37D7:2502 为本次已识别设备的匹配基线，再取得接口号、usage page、报告长度和真实连接方式。该 PID 不足以证明所有接收器或连接模式相同。
2. 优先使用只读 runtime-inspection，检查是否给出发送计数、最后一帧、马达配置帧和错误；仅当现有授权允许时读取相应诊断。
3. 通过低幅度、短时间的单侧、双侧、不同频率和停止实验，对照帧变化。当前还不能据字符串推出具体字节偏移、量化格式、序号、校验和与时序。
4. 将实际设备信息和帧样本与 ApexSenseBridge 锁定版本交叉核验，明确初始化、能力查询、波形编码、发送节奏与停止路径。
5. 原生 Switch 触觉解码仍需独立实现。Engine 的混音和音频分析可以提供硬件基线，但不能直接满足本项目的原生触觉来源目标。
6. PIO USB 选型仍待 USB 描述符与连续包实测；本次没有 USB Audio 必需性或接收器速度的结论。

## 保存的材料

- engine-scan-evidence.json：EXE 指纹、筛选后的协议字符串、历史设备 VID/PID、日志事件计数。排除 UUID、序列号、设备实例路径和令牌。
- engine-api-routes.txt：EXE 静态字符串中的 API 路径清单，包含未经验证的路由；不是可直接执行的请求集。
- work/scan-engine.ps1：可重复执行的只读提取脚本，默认扫描 D:\Engine，仅向当前工作区 outputs 写出筛选结果。

本次未复制厂商二进制、固件或未经筛选的原始日志，未向远端上传材料。
