> 历史阶段记录；当前状态以仓库 docs/HANDOFF_2026-10-22.md 和 docs/STATUS.md 为准。路径及设备序号已脱敏。

# Pico 板型、工具链与最小固件实测

日期：2026-10-22（中国时间）

## 结果

已完成 C/C++ 工具链准备、最小 C 固件编译、RAM 加载与校验、100 次独立 USB 请求应答、Flash JEDEC/SFDP 读取和原有 MicroPython 恢复验证。

## 板卡核实

| 项目 | 结果 | 证据层级 |
| --- | --- | --- |
| 主芯片 | RP2350 A4，QFN60 | picotool 设备查询 |
| CPU 时钟 | 150 MHz | 两个固件运行读取 |
| Flash JEDEC ID | EF4016 | 本次固件向 Flash 发出 0x9F 只读查询 |
| Flash 容量 | 4,194,304 字节，即 4 MiB | Flash SFDP 基本参数表密度字段解码；与 JEDEC 容量字节一致 |
| 原有固件板型标记 | pico2_w | 只描述现有 MicroPython 的编译配置 |
| 第三方整板型号与无线芯片 | 未确定 | 商家型号、原理图或芯片标识仍缺少 |

此前商家标称 2 MB，与工具报告 4 MB 冲突。本次读取了物理 Flash 返回的 SFDP 数据，基本参数表起点 0x80、密度 DWORD 0x01FFFFFF，表示 33,554,432 bit，也就是 4 MiB。现在容量结论有独立于固件布局的设备查询依据；旧记录中的“物理容量待核实”已由本次结果更新。

Wi-Fi 4 与 Bluetooth 5.2 仍仅为商家标称，本次没有启用或测试。使用 `pico2` SDK 基础板型编译是为了验证 RP2350 的 USB 设备端，不代表否认板卡有无线，也不代表完整 Pico 2 W 兼容性已确认。

## 工具链

| 组件 | 固定版本 |
| --- | --- |
| Arm GNU Toolchain | 14.2.Rel1，GCC 14.2.1 |
| Pico SDK | 2.3.1，079c6f39023649b154152db30f1d781e884879bc |
| TinyUSB | 86ad6e56c1700e85f1c5678607a762cfe3aa2f47 |
| CMake | 3.28.1，复用本机已有副本 |
| Ninja | 1.13.2 |
| Python | 3.9.13，复用本机已有副本 |
| picotool | 2.3.1 |

新增工具保存在项目 work/pico-tools，picotool 在 work/picotool-2.3.1。未安装全局软件或修改全局 PATH。为避免 Windows 工具链路径编码问题，在 Documents/Codex 下创建了 pico-work-20261022 和 pico-source-20261022 两个 junction，分别指向本项目 work 和源码交付目录。

Arm ZIP 的 SHA-256 与 Arm 官方 .sha256asc 一致：F074615953F76036E9A51B87F6577FDB4ED8E77D3322A6F68214E92E7859888F。Ninja ZIP 的 SHA-256 与 GitHub 发布资产摘要一致：07FC8261B42B20E71D1720B39068C2E14FFCEE6396B76FB7A795FB460B78DC65。

## 固件与验证

- 配置：RP2350 ARM Secure，PICO_NO_FLASH=1，USB stdio 开启，UART stdio 关闭。
- 源码：pico-minimal-firmware/main.c 与 CMakeLists.txt。
- 生成：pico_usb_smoke.elf 和 pico_usb_smoke.uf2。
- 链接器 size 报告：text 33612、data 0、bss 2372 字节；该统计不等于 UF2 文件大小。
- UF2 文件大小 59,392 字节，共 116 块；所有加载地址位于 SRAM 0x20000000–0x20007400，无 Flash 加载目标。
- picotool 明确显示 Loading into RAM 和 Verifying RAM，校验 OK，随后成功启动。
- RAM 固件枚举为 COM12，INFO 回应程序名、SDK 2.3.1、150 MHz 与 no_flash=1。
- 100 次独立随机标记的 PING/PONG 均准确匹配，100/100 通过。
- 本轮主机端请求应答耗时：最小 0.373 ms、平均 0.464 ms、最大 1.636 ms。包括 Windows、PowerShell 和 USB CDC 调度，未作实时性保证，不能作为游戏输入或马达响应延迟。
- JEDEC 与 SFDP 查询成功。仅发只读命令，不执行 program/erase。
- REBOOT 后恢复 COM11；再次执行原有 MicroPython 测试成功，版本、150 MHz 和十条计算结果正常。

未重新烧录、擦除或写入板上测试文件。已有 Flash 备份仍保存在 work/pico-before-test-20261022.bin。本次没有在测试后重新逐字节比较全部 Flash，因此不作“前后全盘哈希相同”的额外声明。

## 当前可继续的工作

基础 C 固件与 USB 设备端工具链已通过，可以继续接入面向主机的手柄协议实验。完整阶段 0 尚未结束：无线芯片与 SDK 适配、外部 GPIO/UART、恢复操作覆盖和长时间稳定性仍待测试。USB 主机／PIO USB、飞智接收器、Switch 2 识别和原生触觉闭环均未验证。

原始实测输出：pico-native-test.txt、pico-usb-repl-test.txt。源码和 RAM 固件集中在 pico-minimal-firmware/。

官方参考：

- https://github.com/raspberrypi/pico-sdk/tree/2.3.1
- https://github.com/raspberrypi/picotool
- https://github.com/raspberrypi/pico-vscode/blob/main/data/0.18.0/supportedToolchains.ini
