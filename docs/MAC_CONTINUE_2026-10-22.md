# macOS 接续指南

先读 [详细交接](HANDOFF_2026-10-22.md)。本次交接提供源码和筛选证据，**没有宣称 Windows 硬件控制脚本已移植为 Mac 版本**。

## 1. 取回仓库与纯离线检查

旧 Mac 目录可能与 GitHub 历史不一致。优先另建目录，不删除旧工作，也不强制 reset：

```sh
git clone https://github.com/Qzq66/-flydigi-switch2-haptics-bridge.git flydigi-switch2-resume
cd flydigi-switch2-resume
python3 tools/run_offline_checks.py
```

离线检查不打开 USB、不发送网络包、不驱动马达，无第三方 Python 包依赖。检查报告是在本次上传前的 Windows Python 上执行所得，Mac 的实际执行结果请另存，不把它当成本次已测试过 macOS。

当前文件布局：

```text
docs/HANDOFF_2026-10-22.md        真实状态、证据、限制、恢复方法
docs/PROTOCOL_NOTES_2026-10-22.md 数据包与结束确认
handoff/2026-10-22/work/          Windows原型、纯处理模块、测试
handoff/2026-10-22/outputs/       三组固件源码、筛选后的历史记录/证据
handoff/2026-10-22/SOURCE_MANIFEST.json  本机源/公开副本 SHA256 清单
tools/macos_hid_probe.swift      原仓库已有的只读 Mac HID 探测
tools/build_pico_snapshot.py     跨平台构建入口（只编译、不烧写）
```

历史脚本的 ROOT/outputs 相对结构保留在快照内。不要把这些脚本零散复制到仓库根目录后运行。代码中 `WINDOWS_USER`、`PICO_SERIAL_REDACTED`、`SESSION_REDACTED` 是公开副本占位符，不能原样当真实参数使用。

## 2. Pico 编译准备

本机验证过的 SDK 是2.3.1，ARM GCC14.2.1。Mac 工具版本可能不同，应记录版本并重新核对生成物，不期待二进制哈希相同。

按 [Raspberry Pi 官方 C SDK 文档](https://www.raspberrypi.com/documentation/microcontrollers/c_sdk.html) 配置 CMake、Ninja、ARM 工具链；需要 brew 时参考 [Ninja](https://formulae.brew.sh/formula/ninja) 与 [Arm 工具链](https://formulae.brew.sh/cask/gcc-arm-embedded) 的官方包说明，包版本会变，不把当前包版本等同于已验证的 Windows GCC。

SDK可固定到交接版本，放在仓库外：

```sh
git clone --branch 2.3.1 --depth 1 https://github.com/raspberrypi/pico-sdk.git ../pico-sdk-2.3.1
git -C ../pico-sdk-2.3.1 submodule update --init --depth 1
export PICO_SDK_PATH="$(cd ../pico-sdk-2.3.1 && pwd)"
arm-none-eabi-gcc --version
cmake --version
ninja --version
```

使用 `pico2_w`、`rp2350-arm-s`，实际 Flash4MiB。快照 CMake 把原来的固定 Windows 私密头文件路径改为 `BRIDGE_PRIVATE_DIR`，默认为快照 `work/private`。该目录未上传，先在本机创建 `bridge_credentials.h`；可从同目录的 example 文件复制，填写本机专用测试网络。不要提交真实值。用于编译的占位符固件不能入网。

```sh
mkdir -p handoff/2026-10-22/work/private
cp handoff/2026-10-22/work/bridge_credentials.example.h handoff/2026-10-22/work/private/bridge_credentials.h
# 用本地编辑器填写专用测试网络；不要在共享终端录屏中显示密码。
python3 tools/build_pico_snapshot.py --variant v042 --profile ram
```

入口只调用配置/编译与镜像边界验证，不调用 picotool load。SDK2.x 的 ELF/UF2 转换涉及 picotool；依赖来源及安装方式参考 [官方 picotool 构建文档](https://github.com/raspberrypi/picotool/blob/master/BUILDING.md)。如无法构建，保存诊断，不改用未知第三方固件。

v042只有Windows RAM验证，尚无Mac构建或Flash实测。Flash BIN必须在0xe0000之前，绝不能覆盖日志区/原文件系统。不要把RAM UF2当Flash安装镜像，也不要用旧的v040固定哈希脚本安装新版本。

## 3. 硬件运行前必须移植的部分

| 文件/依赖 | Windows实现 | Mac待办 |
| --- | --- | --- |
| flydigi-readonly.py | 固定 `D:\Engine\firmware\hidapi.dll`、kernel32/hid、HidP_GetCaps | 使用IOHID/HIDAPI适配；核对句柄/枚举ABI及report ID语义 |
| xinput_readonly.py | XInput1_4.dll，只读槽位 | macOS无此接口；先被动探测输入来源，不能擅自开启持久接管 |
| child/guardian时序 | winmm、CREATE_NO_WINDOW | 替换为Mac进程/计时实现，保留异常退出监护和停止确认 |
| 热点脚本 | PowerShell WinRT/DPAPI | 新网络与私密凭据本地重新配置，不能解密原DPAPI |
| 网络Client/discovery | 绑定/广播192.168.137.x | 同时调整电脑绑定、广播和固件允许的电脑IPv4；不可只改SSID |
| 设备选择 | 固定原机板卡序号/COM11 | 重新枚举实际板卡/串口，核对唯一身份，不按VID/PID随便烧写 |

原 Swift 查询可先使用，保留只读范围；见 [旧 Mac 记录](MAC_RECEIVER_DIAGNOSIS.md)。需要输入监控时使用正常系统授权，不默认需要 sudo，不关闭安全保护。HIDAPI 的接口/构建参考 [上游文档](https://github.com/libusb/hidapi/blob/master/BUILD.cmake.md)。

不能直接运行 `bridge-switch-live.py --help` 就认为没有硬件依赖：它目前会在解析参数前导入 Windows HID 模块。跨平台纯模块测试入口才是安全起点。

## 4. 原件需要私密转移

原Pico4MiB镜像、手柄RAM备份、原设备序号、Wi-Fi凭据/会话令牌没有公开上传。开始任何持久烧写前，从原Windows私密获取原Flash备份，SHA256必须匹配详细交接中的值。公开的JSON只是结果记录，不是可恢复镜像；DPAPI备份不是Mac可读密码文件。

## 5. 下一次实际测试

先补游戏模式和终止标记的离线检查，再做无输出的 Mac 接收器/输入探测、Pico RAM UDP/末帧确认、输入断线回中，然后有独立监护进程的短输出。最后才恢复真实主机游戏测试。

游戏计划是《空之轨迹2nd》，用户尚未用原装手柄确认具体震动动作。确认之前不把“没有震动”归因于桥接；不能把登记页两个提示当作游戏内证据。用户暂停硬件测试的状态在此次同步后仍有效。
