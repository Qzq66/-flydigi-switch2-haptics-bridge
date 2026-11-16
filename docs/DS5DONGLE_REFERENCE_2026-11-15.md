# DS5Dongle参考核对：单USB口蓝牙桥接

核对日期：2026-11-15。用户提供 https://github.com/awalol/DS5Dongle/releases ，要求先参考PS5手柄无线接电脑的实现。本次仅阅读发布说明/源码，没有下载或烧写UF2，没有运行上游自动安装脚本，没有修改现有SDK或设备。

## 结论与路线更正

单个USB口不是“USB设备端 + 板载蓝牙”的障碍。DS5Dongle给出了Pico2W通过CYW43经典蓝牙连接DualSense、通过原生USB向电脑模拟有线手柄的实现。此前把GPIO外接原装USB接收器置于优先位置过早；那只适用于继续使用USB接收器的路线。

新的优先验证路径是：

`离线Switch 2 ↔ Pico原生USB设备端 ↔ 板内协议处理 ↔ CYW43蓝牙 ↔ 飞智手柄`

这条路线不要求第二个USB口、电脑转发或电脑热点，但飞智蓝牙输入及精细波形输出均未实测。DS5示例不证明飞智蓝牙端接受此前USB/接收器上的0x57波形，也不证明主机会接受Sony身份。GPIO USB Host组件保留为备用，不要求用户现在加线或买板。

## 本次绑定版本与源码证据

本次GitHub latest为[v0.8.0](https://github.com/awalol/DS5Dongle/releases/tag/v0.8.0)，发布时间2026-10-28，标签解析到提交 `77d378effcda11abee87f9be1ac31d6518e87560`。具体文件Git blob ID见同目录campaign的 `ds5dongle-reference.json`，不依赖滚动master结论。

| 可核对结论 | 具体源码位置 | 对本项目的意义 |
| --- | --- | --- |
| 使用USB设备端而不是第二条USB主机口 | `src/main.cpp:334` 设备角色初始化，`:408` CYW43轮询与`:409` tud_task并行；`CMakeLists.txt:355` BTstack Classic、`:358` CYW43 HCI、`:359` tinyusb_device | 单口蓝牙桥接框架可参考 |
| HID控制/中断采用经典蓝牙L2CAP通道 | `src/bt.cpp:144` 初始化，`:149`/`:150`注册服务，`:105`/`:111`分别发送中断/控制包 | 连接管理/通道/缓冲框架可参考；Classic与BLE不能混同，先识别飞智实际服务 |
| 发现结果限定DualSense名称 | `src/bt.cpp:383`至`:389` | 原版不识别飞智；不能只改名称过滤就算完成支持 |
| PC侧模拟Sony设备 | `src/usb_descriptors.cpp:116` Sony VID，`:131` DS/Edge PID选择 | 本项目保留已验证的一代Pro兼容设备端，不照搬Sony描述符 |
| 输入与触觉报文是DualSense专用 | `src/main.cpp:79` 输入0x31、`:213`至`:220`输出0x31；`src/audio.cpp:32`至`:36`定义0x36/0x39/0x32音频/触觉报告 | 不能直接发给飞智；不能用Opus路径代替飞智波形协议 |
| 音频处理使用第二核心 | `src/audio.cpp:447`启动core1，`:525`起进行Flash安全登记；`CMakeLists.txt:299`设PICO_FLASH_ASSUME_CORE1_SAFE=0 | 不可沿用v043“core1未启动所以安全”的Flash日志假设 |

参考源码：[main.cpp](https://github.com/awalol/DS5Dongle/blob/77d378effcda11abee87f9be1ac31d6518e87560/src/main.cpp)、[bt.cpp](https://github.com/awalol/DS5Dongle/blob/77d378effcda11abee87f9be1ac31d6518e87560/src/bt.cpp)、[audio.cpp](https://github.com/awalol/DS5Dongle/blob/77d378effcda11abee87f9be1ac31d6518e87560/src/audio.cpp)、[USB描述符](https://github.com/awalol/DS5Dongle/blob/77d378effcda11abee87f9be1ac31d6518e87560/src/usb_descriptors.cpp)、[CMakeLists](https://github.com/awalol/DS5Dongle/blob/77d378effcda11abee87f9be1ac31d6518e87560/CMakeLists.txt)。

## 直接移植前需要处理的差异

- 当前上游英文README和Pico2W的CMake配置为150MHz，中文README仍写320MHz/1.2V。说明存在不一致，按具体源码/构建参数核对，不照旧中文说明超频。
- 上游要求Pico SDK 2.3.1、TinyUSB `98741b55959564746998d0453c32d87064629d7c`；现有验证环境的TinyUSB为 `86ad6e56c1700e85f1c5678607a762cfe3aa2f47`。它的构建脚本会准备/切换依赖，不能在原冻结SDK上直接运行。若移植，使用隔离依赖目录，先决定是否实际需要其新TinyUSB功能。
- 本地SDK当前缺BTstack源。先补齐SDK绑定版本/隔离依赖，再构建最小蓝牙探针；不以静态USB组件编译成功冒充蓝牙固件已完成。
- 不复制音频输入、麦克风、扬声器、键盘唤醒、宏、自动恢复与持续重试。当前目标是Switch参数事件与飞智输出，不需要PC USB Audio/Opus全栈。
- 上游MIT许可允许参考/移植，但实际复制代码时须保留版权和许可；原v043其他来源许可保持不变。
- 原版固件具有自己的配对/配置Flash布局。即使已获用户烧录授权，也不能直接覆盖Pico已有日志/配对区而不先备份、核对镜像及分区。此项是保存现有成果的需求，不是要求重新授权已授权的烧录。

## 下一项具体交付

制作隔离的“蓝牙发现 + 只读输入”候选，先验证飞智采用Classic HID还是BLE HID、设备标识、报告描述符和实际输入数据。发现阶段不发送未知初始化/接管/马达命令，不自动把Sony报文换名后发送给飞智。

后续把已验证的Switch USB设备端接入蓝牙输入转换；精细震动保持独立协议闸门：获得飞智蓝牙输出格式或可证实的协议支持，再移植双频波形与停止保护。若蓝牙只支持输入/普通震动，明确报告限制后与用户决定是否接受，而不以“能配对”宣称细腻震动已完成。

本次未移植运行代码、未编译DS5Dongle、未访问设备，没有新增硬件测试或保真通过结论。用户已允许为接收用途烧录；此轮“先参考”已完成，后续只有在目标固件可审查、设备备份及连接状态核对完成后才实施。