# 飞智接收器只读输入组件（仅交叉编译）

此目录尚不是固件，没有main/ELF/UF2，不可烧录。当前只证明针对本地Pico SDK 2.3.1、TinyUSB固定版本和RP2350目标能编译独立输入驱动；没有设备实测。

仅匹配37D7:2502、全速、ff/5d/01接口。由实际描述符选择唯一中断IN端点，包长最多64字节，收满32包停止；传输失败停止，不重试。没有飞智vendor/control输出、震动、改配置或XInput启动命令。不把原始USB包当作Windows XINPUT_GAMEPAD。USB核心正常枚举所需的标准控制请求不等同于飞智配置写入。

构建结果见 `../../docs/campaigns/realtime-2026-11-15/standalone-receiver-build.json`。`build-ascii/libreceiver_input_probe.a`包含SDK静态对象与调试信息，大小不是固件运行占用；自身驱动对象text=788B、bss=2166B，最终链接占用尚未测量。

本地Pico-PIO-USB与BTstack底层依赖缺失。当前静态依赖用原生USB Host配置，尚无“原生USB设备端+PIO Host”的并行整合，也没有电源/引脚/多核/Flash日志方案。默认只读轮询若收不到输入，不能自动发送未知初始化命令。

用户已允许为接收用途烧录Pico，但最终接法仍需确定。单个C口面向Switch时，原装USB接收器需要GPIO PIO USB外接接口或其他独立Host硬件；普通集线器不能代替。直接蓝牙到手柄是另一条未验证输入及精细震动协议的路线，不能把此USB组件描述成蓝牙接收固件。

## 本机重建

通过现有ASCII路径别名避免GCC汇编器输出路径乱码，不移动SDK。CMake关闭picotool自动依赖、FetchContent联网；不执行picotool，也不访问设备。

```powershell
$cmake = 'D:\GPT-SoVITS-v2-240821 AI语音\runtime\Lib\site-packages\cmake\data\bin\cmake.exe'
& $cmake -S standalone/receiver_probe -B standalone/receiver_probe/build-ascii -G Ninja '-DPICO_SDK_PATH=C:/Users/quziqi/Documents/Codex/pico-work-20261022/pico-tools/pico-sdk' '-DPICO_TOOLCHAIN_PATH=C:/Users/quziqi/Documents/Codex/pico-work-20261022/pico-tools' '-DCMAKE_MAKE_PROGRAM=C:/Users/quziqi/Documents/Codex/pico-work-20261022/pico-tools/ninja/ninja.exe'
& $cmake --build standalone/receiver_probe/build-ascii --target receiver_input_probe --parallel 2
```