# PRO2 Bridge v2.9参考核对

日期：2026-11-15。用户补充LeonChrome/XinHeLianSheng-Pro2-Bridge及v2.9 EXE链接。本次读取发布说明与对应源码，未下载/运行约120MB的EXE，未改驱动、蓝牙参数、手柄配置或Pico。仓库main首页已提到v3.2.1；下面结论绑定用户提供的 `pro2-v2.9`，提交 `ed148a9462d6f65946b737ee8c879d17e41f581b`，不混用滚动main。

## 结论

这个例子提供了公开的NS2 Pro蓝牙震动编码及PS5触觉转换实现。它可以作为无线触觉协议适配的参考，但不能据此认定飞智蓝牙能接受同一种输出。

- DS5Dongle：Pico通过经典蓝牙HID/L2CAP连接DualSense，通过USB设备端模拟有线Sony手柄。
- PRO2 v2.9：Windows通过BLE/GATT连接实体NS2 Pro，通过USBIP/VIIPER向游戏提供虚拟手柄；PS5普通震动与触觉音频被转换为NS2 Pro输出。
- 本项目：Switch 2通过USB连接Pico，由Pico通过飞智实际支持的蓝牙模式读取输入并返回震动。单C口的结构可继续验证，但飞智具体服务、报告及波形能力仍是未关闭的缺口。

这两份参考降低了“单板USB + 蓝牙能否工作”的架构不确定性，没有替代飞智端协议验证。不再以电脑CPU回放作为主线，也不先要求用户购买USB Host硬件。

## v2.9源码的实际输出路径

主要文件前缀为 `source/final-three-in-one/windows/v60_viiper_app/`：

| 事实 | 源码位置 |
| --- | --- |
| BLE FD2输入、命令、ACK及震动特征分别定义，震动UUID为cc483f51-9258-427d-a939-630c31f72b05 | `Pro2BleInputSource.cs:161`至`:165` |
| 将队列中的震动包写到实际GATT特征，并按特征能力选择有响应/无响应写 | `Pro2BleInputSource.cs:3741`、`:3762`、`:3925`至`:3934` |
| raw02中间报告64字节，BLE输出33字节，转换路径要求两个已知0x50马达块 | `Pro2BleRumblePacketEncoder.cs:13`至`:14`、`:31`至`:38` |
| 原生USB反馈与BLE共享左右两个16字节马达块；单位增益路径保留32字节载荷，只调整包ID | `Pro2NativeRumbleEncoder.cs:6`至`:11`、`:29`至`:30` |
| 已知格式每侧包含三个5字节子帧，四个10bit参数槽位，增益仅修改幅度位 | `Pro2NativeRumbleEncoder.cs:16`、`:48`至`:57` |
| PS5品质转换把四通道48kHz PCM的第3/4通道作为左右执行器，降至3kHz分析、低高频各提取一组幅度/频率 | `Pro2QualityHapticProcessor.cs:7`至`:13`、`:34`至`:38`、`:107`至`:108` |
| 品质转换96样本分析窗、36样本步长；同批次多个结果仅返回较新状态，不延迟重放PCM积压 | `Pro2QualityHapticProcessor.cs:12`、`:53`至`:61` |

这是“PS5触觉PCM → 左右双频参数 → NS2 Pro专用BLE包”，不是把PS5 PCM逐样本原样交给实体Pro2。原生NS2 Pro载荷转发和PS5合成反馈是不同路径，不能混称。

尤其需要保留上游边界：

- `Pro2RumbleFrequencyPolicy.cs:5`至`:13`明确表示控制值到物理Hz没有独立校准，标记为 `legacy_hz_proxy_unvalidated`。不能把估计频率/协议字段当实测机械频率。
- `Pro2RumbleOutputQueue.cs:15`明确为有损事件选择，不是PCM重采样或播放保证。不能复制其丢弃/适配策略后声称本项目原始时序完全保真。
- 此项目中33字节是NS2 Pro BLE封装；本项目飞智Windows接口的33字节是另一种报告语义，长度相同不代表协议通用。

## 仓库Pico目录不是现成的目标固件

`source/final-three-in-one/README.md:5`将ESP/Pico目录标为历史参考。`firmware/pico2w_pro2_wireless_bridge/README_ZH.md`描述的路径为“真实Pro2 USB → Pico → 无线模拟Xbox/PS5/Edge/Switch1”，方向不同，并明确只做普通强弱震动、不提供DualSense音频HD触觉。它还需要GPIO上的PIO USB Host接口。

所以不能将这个历史Pico固件直接刷入，期待其接收飞智蓝牙或还原精细震动。它可作为另一种主机/外设角色与USB Host实践的参考。

## 对当前实现的取舍

1. 保留已验证的一代Pro兼容Switch USB端与震动参数接收。完整NS2 Pro/HD Rumble 2身份不因本参考而变成已完成。
2. 优先隔离实现Pico蓝牙发现与只读输入，判明飞智是Classic HID、BLE HID还是其他服务；仅识别到设备名不算输入验证。
3. 我们的上游已是主机震动参数，不需要照搬PS5 48kHz PCM频谱分析。尽量直接保留参数语义，避免不必要的计算与有损转换。
4. 震动输出需获得飞智蓝牙特有格式或可验证支持；不向飞智发送Sony报告、任天堂GATT UUID/初始化命令，或未经验证的USB 0x57移植包。
5. 不引入该Windows程序的驱动、虚拟USB、全局BLE参数优化、自动重连/重试或配置写入逻辑。已有保护不因参考项目的参数不同而放宽。

本次只做源代码参考，代码尚未整合，未新增硬件验收。上游仓库标为Apache-2.0；实际复制源码前应保留许可并核对各组件来源，本次仅记录协议事实与实现边界。

参考：[v2.9发布](https://github.com/LeonChrome/XinHeLianSheng-Pro2-Bridge/releases/tag/pro2-v2.9)、[版本源码](https://github.com/LeonChrome/XinHeLianSheng-Pro2-Bridge/tree/ed148a9462d6f65946b737ee8c879d17e41f581b)、[品质转换](https://github.com/LeonChrome/XinHeLianSheng-Pro2-Bridge/blob/ed148a9462d6f65946b737ee8c879d17e41f581b/source/final-three-in-one/windows/v60_viiper_app/Pro2QualityHapticProcessor.cs)、[原生参数编码](https://github.com/LeonChrome/XinHeLianSheng-Pro2-Bridge/blob/ed148a9462d6f65946b737ee8c879d17e41f581b/source/final-three-in-one/windows/v60_viiper_app/Pro2NativeRumbleEncoder.cs)。源文件blob清单及发布资产声明摘要见 `campaigns/realtime-2026-11-15/pro2-bridge-reference.json`；未下载EXE，因此其SHA256仅为发布方声明，并非本地文件核验。