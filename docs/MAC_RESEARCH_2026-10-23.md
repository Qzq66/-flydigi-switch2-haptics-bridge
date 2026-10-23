# Mac 资料收集：窗口、日志与原生协议

收集日期2026-10-23，项目基准cf012409cfe27da38cc5bd6f06ba7276b7ca4613。以下区分源码事实、外部研究与本项目推论。本阶段不改固件/保护参数、不安装第三方驱动、不运行资料中的硬件命令。

## 1. 优先：延长窗口不是改单个60秒常数

基准源码定位（均为本仓库路径）：

| 位置 | 当前约束 | 候选设计必须回答 |
| --- | --- | --- |
| outputs/pico-haptics-bridge-v042/main.c（在handoff/2026-10-22下） | 就绪后约60000ms、启动总计120000ms、最终240000ms兜底；登记调度另有115000门槛 | 从何时计时，登记与正式游戏是否共用预算；末尾保留多少收尾时间 |
| 同目录bridge_transport.c | draining后ACK排空、BHE2确认及50ms应答保留；main排空上限1000ms | 正常、迟到、丢确认、客户端先退出都能结束且不丢尾帧 |
| work/bridge-switch-live.py（同handoff根） | 发现120s、game live62s、阶段状态deadline=start+58、排空1.5s | 电脑、Pico、启用按钮截止时刻是否相容 |
| work/flydigi-live-bridge-bench.py | 游戏父进程等待200s | 必须覆盖发现＋操作＋排空＋独立关闭，不能先被父进程强杀 |
| tools/game_arm_window.py | 距deadline不足5s不接受启用，GUI周期更新 | 候选截止值必须与后端一致，不单独延长按钮显示 |
| capture_journal.c/.h | 65536字节槽、128字节头、末尾4字节CRC、24字节记录 | floor((65536−128−4)/24)=2725条，是USB记录总量而非仅马达数 |

两个槽轮换保存不同世代，不等于本轮可存5450条。没有改变格式时，一轮仍限2725条。按假设125条/秒估算，约21.8秒就可填满；这是压力预算示例，不是已测报文速率。两轮门口场景仅约565/583条总记录，不能据此给持续动作的数分钟游戏做容量保证。

候选资料结论：先维持原格式和完整性要求，明确预留登记/结束记录容量；接近容量时做可解释的有界结束是值得评估的方案。要提高容量、压缩或流式分段则需独立日志版本、内存与Flash布局审查，不能静默覆盖前缀或把截断记作完整。暂不确定延长到几分钟，先用现有捕获计算峰值/滑窗计数并补最坏流量模型。

## 2. Pico网络与Flash执行约束

[Pico SDK 2.3.1 cyw43_arch.h](https://github.com/raspberrypi/pico-sdk/blob/2.3.1/src/rp2_common/pico_cyw43_arch/include/pico/cyw43_arch.h)说明poll模式需主循环周期服务，且不是多核/IRQ安全接口。因此延长日志或加入阻塞操作时，应分析服务间隙；不能凭平均UDP吞吐量推断80ms保护始终满足。此为对本项目的推论，未测新时序。

[Pico SDK 2.3.1 flash.h](https://github.com/raspberrypi/pico-sdk/blob/2.3.1/src/rp2_common/pico_flash/include/pico/flash.h)提供flash_safe_execute安全执行接口，Flash与XIP/中断执行需协调。本项目目前在结束阶段落盘；若改为边玩边写，需要另审USB/Wi-Fi服务、心跳与断电一致性，不应直接把结束阶段写入搬进实时循环。SDK证据固定为2.3.1，不擅自升级成功基线。

## 3. 高保真：先分清解码和物理输出

[MissionControl 0.12.0作者说明](https://github.com/ndeadly/MissionControl/discussions/873)记录HD rumble存在额外打包格式，解码曾整体重写。当前项目Python解码器已经标明GPL-2.0-only和其参考提交71bbe2d4e97d618775b5a3e2f91bfeaf52d8b75e；后续复用保留许可证和来源，不能只拿早期单组公式替换状态解码。

Mac可先做：对现有真实捕获建立频率/幅度参数分布、状态缺失和压缩分组时序的证据表。5ms/组仍是本项目实验假设，不是物理校准；1kHz输出对≥500Hz的原波形还原有采样限制。当前提示模式左右固定160/320Hz、120ms，不提供原始波形保真证据。物理频响、马达振幅、输出采样率与端到端延迟仍要设备测量，资料推导不能替代。

## 4. 原生NS2 Pro无线：有新资料，但不能直接套用

一手研究入口：[ndeadly/switch2_controller_research](https://github.com/ndeadly/switch2_controller_research)。本次核对HEAD `a3306b473acff0d6844fb1e288883a3940df0baf`，优先固定该提交阅读：

- [bluetooth_interface.md](https://github.com/ndeadly/switch2_controller_research/blob/a3306b473acff0d6844fb1e288883a3940df0baf/bluetooth_interface.md)：作者记录原生Switch 2控制器使用BLE、自定义广告/GATT与配对，不是通用HID over GATT；普通系统配对不能视作原生兼容方案。
- [hid_reports.md](https://github.com/ndeadly/switch2_controller_research/blob/a3306b473acff0d6844fb1e288883a3940df0baf/hid_reports.md)：Pro2的报告布局和GATT传输有对应关系，蓝牙端不直接携带USB report ID；它与当前Pro1兼容USB输出字段不是同一个协议证明。

这是开发者逆向研究，不是任天堂完整官方规范。对本项目的推论：Pico蓝牙版本数字只能说明部分射频/栈能力，尚需逐项验证广播、GATT外围角色、配对持久状态、主机初始化、重连及输出格式。即使能连接真Pro2，也不等于能在主机前模拟Pro2；真机兼容和震动支持必须独立验收。

## 5. 重读最初PRO2桥接参考：方向很关键

[PRO2助手v1.3.22](https://github.com/LeonChrome/XinHeLianSheng-Pro2-Bridge/releases/tag/pro2-v1.3.22)和[README](https://github.com/LeonChrome/XinHeLianSheng-Pro2-Bridge/blob/f01ae1cf7accf457f65002dc5e2ab3fdcd42572a/README.md)（本次main为f01ae1cf7accf457f65002dc5e2ab3fdcd42572a）明确是Pro2经BLE连接Windows，再提供PC兼容输出及PS5触觉转换；作者同时限制了对完整DualSense和跨设备蓝牙转发的宣称。

可借鉴分层输入、兼容设备输出与触觉转换架构；不能据此证明“飞智→Switch 2主机”的反向模拟已经实现。当前没有阅读完其全部触觉转换源码，也没有核实其PS5路径的数据传输细节，不将README当完整算法。后续只挑源码中报告变换和触觉接口做带文件路径的核对，不运行EXE或全局蓝牙优化。

## 6. Mac下一批可交付内容（尚未执行）

1. 已有新世代捕获的滑动窗口速率/峰值/日志预算表；注明统计USB记录还是马达事件。
2. 候选配置表：固件live、boot、兜底、主机发现/live/guardian、GUI截止、排空与容量联动。
3. 故障与容量验收清单：满槽前后、重启、尾帧、丢ACK、静音后输入、重复启用、到期停止；保持80ms、±12、120ms和每侧3次边界。
4. 原生BLE与Pro1 USB兼容两条路线的需求差异表；原波形解码/合成/马达物理校准分开验收。

本次只完成阅读与归档，没有生成候选实现或新实测数据。成功基线不动；后续开发使用独立候选，不直接覆盖当前已验证程序。
