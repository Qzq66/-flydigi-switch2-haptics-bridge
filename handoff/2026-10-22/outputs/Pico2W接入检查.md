> 历史阶段记录；当前状态以仓库 docs/HANDOFF_2026-10-22.md 和 docs/STATUS.md 为准。路径及设备序号已脱敏。

# Pico 板卡接入检查

后续更新：同日已编译并实测 RAM 最小 C 固件，100 次 USB 应答通过；Flash JEDEC=EF4016，SFDP 确认 4 MiB；原有 MicroPython 恢复通过。完整结论见 Pico2W最小固件测试结果.md。以下保留早期检查过程，其中“容量待核实”和“工具链未准备”的历史状态已被后续结果更新。

日期：2026-10-22（中国时间）

本次通过 Windows 设备枚举及启动盘文件只读检查确认：

- 启动盘：G:，卷标 RP2350。
- USB VID/PID：2E8A:000F；RP2350 Boot 接口状态 OK。
- INFO_UF2.TXT 内容：UF2 Bootloader v1.1；Model: Raspberry Pi RP2350；Board-ID: RP2350。
- 初次检查处于 BOOTSEL／UF2 启动模式，电脑能够识别芯片 ROM USB 启动接口；后续测试已重启到现有 MicroPython，见下文。
- 启动盘只提供 UF2 拖放入口；Windows 显示约 128 MiB 的卷大小不能用来认定实际 Flash 容量。

尚未验证：第三方整板型号、物理 Flash 容量、无线芯片及无线功能、GPIO 布线、Pico SDK 板型兼容性、手柄模拟与触觉桥接。现有应用固件运行已通过下述最小测试。

当前 PATH 未找到 picotool、CMake、arm-none-eabi-gcc；这不能证明其他目录没有安装。系统列有多个 COM 口，本次未将任何一个归属到 Pico。

初次检查未烧录固件、未写入启动盘。后续执行情况如下。

## 同日后续：工具链与现有固件最小测试

- 已从 Raspberry Pi 官方 pico-sdk-tools v2.3.1-0 下载便携 picotool 2.3.1，在项目 work 目录解压，不修改系统 PATH。ZIP SHA-256 已与 GitHub 发布资产摘要核对一致：68730BE0813F8F35BE2CCA147CF7F1572662D5DCF0F5BA468E02A6DD9E85DB2B。
- 本机另找到可用 CMake 3.28.1 和 Python 3.9；未找到 ARM GCC 和 Pico SDK。本次未建立 C/C++ SDK 编译环境。
- picotool info -a：RP2350 A4，QFN60，flash size 报告 4096K；现有固件为 MicroPython v1.25.0-preview.49.g0625f07ad.dirty（2024-11-21），构建板型 pico2_w，SDK 2.0.1-develop。
- 现有固件的文件系统地址配置为 0x10100000–0x10400000，3 MiB。这是固件布局，不是物理容量的独立证明。
- 先只读导出 4 MiB 地址范围并通过 picotool -v 读回校验。备份留在 work/pico-before-test-20261022.bin；SHA-256 为 09762691D3FDDF3BA592DB0BB6F520CB2384423F37194E7974089C9B0F700593。该文件是读出地址范围备份；真实容量仍待核对。
- 重启已有应用成功，USB 串口枚举为 COM11，VID/PID 2E8A:0005。
- 经 USB REPL 在 RAM 中执行测试，CPU 150 MHz，GC 可用内存 451792 字节；连续返回 10 条正确的 sum(range(1001))=500500 结果。完整输出见 pico-usb-repl-test.txt。
- 测试通过的是现有固件启动、RAM 代码执行和 USB CDC 通信。不是 10 次独立请求往返的延迟测试，也没有验证硬件 UART。
- 没有重新烧录、擦除、写入板上测试文件、启用无线或操作外部 GPIO。测试后保留在现有 MicroPython 应用模式。

## 商家参数与冲突记录

用户补充商家标称：Flash 2 MB；Wi-Fi 2.4 GHz 802.11n（Wi-Fi 4）；Bluetooth 5.2。未提供具体板卡型号、原理图或无线芯片标识。

商家 2 MB 与 picotool 报告 4 MB 存在冲突，暂不作真实容量结论。Pico SDK 的 FLASH_DEVINFO 可由运行时或构建板型参数设置，不能用配置值或所存固件的文件系统边界独立证明 Flash 容量。对 4 MiB 备份做只读比较时，前后两个 2 MiB 块不完全相同；这仅排除了该次读出结果完全镜像的情况，未替代 JEDEC/SFDP 或芯片料号核对。

在冲突解决前，不进行高地址写入或按 4 MB 规划新固件。下一步需要板卡型号、Flash／无线芯片标识或商家原理图，核实后再推进无线、GPIO 和 C/C++ 固件构建。

官方参考：https://github.com/raspberrypi/pico-sdk/blob/master/src/rp2_common/hardware_flash/include/hardware/flash.h
