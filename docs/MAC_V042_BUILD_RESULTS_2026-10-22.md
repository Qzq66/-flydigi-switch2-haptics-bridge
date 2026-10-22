# 第五步：Mac 编译 Pico v042（未烧写）

2026-10-22，在Apple Silicon Mac完成RAM与Flash两个Release构建，固件C源码未修改。只执行编译、ELF/UF2转换、镜像与符号核对，没有连接设备、加载固件或修改热点/手柄。此次允许下载构建依赖；构建不属于网络完全离线过程。

## 工具与来源

- [Raspberry Pi Pico SDK 2.3.1](https://github.com/raspberrypi/pico-sdk/tree/2.3.1) 官方tag归档，依赖按该tag锁定的TinyUSB、CYW43、lwIP提交提取。不是完整Git子模块checkout；依赖提交与归档哈希见JSON报告。
- Arm GNU Toolchain 14.2.Rel1，GCC14.2.1 20241119，darwin-arm64；[Arm官方下载](https://developer.arm.com/-/media/Files/downloads/gnu/14.2.rel1/binrel/arm-gnu-toolchain-14.2.rel1-darwin-arm64-arm-none-eabi.tar.xz)。下载SHA256与同地址 `.sha256asc` 官方校验文件一致：`c7c78ffab9bebfce91d99d3c24da6bf4b81c01e16cf551eb2ff9f25b9e0a3818`。
- CMake3.31.6、Ninja1.13.0，安装于本地忽略的build/tooling/venv，没有系统安装。
- [picotool2.3.1](https://github.com/raspberrypi/picotool/tree/2.3.1)，本机AppleClang构建；明确启用PICOTOOL_NO_LIBUSB=1，无USB操作支持，仅用于文件转换。未加入mbedTLS签名/哈希支持；镜像SHA256由Python计算，不宣称安全签名。
- SDK、工具、镜像与完整构建日志均在被忽略的build目录，不上传。

## 结果与边界

| 项目 | RAM | Flash |
| --- | --- | --- |
| 目标 | pico2_w / rp2350-arm-s | 同左 |
| 配置Flash | 4194304字节 | 同左 |
| PICO_NO_FLASH | 1 | 0 |
| 镜像 | UF2，609280字节，1190块 | BIN，306036字节 |
| 镜像地址区间（右端不含） | 0x20000000–0x2004a600 | 0x10000000–0x1004ab74 |
| ELF静态区结束 __end__ | 0x20061608 | 0x2001880c |
| HeapLimit / StackTop | 0x20080000 / 0x20082000 | 同左 |
| Flash擦除对齐范围（偏移） | 不适用 | 0x0–0x4b000 |
| flash_range_erase/program符号 | 不存在 | 存在，符合持久日志设计 |

RAM的UF2结构、块号、唯一地址、RP2350 ARM secure家族ID与SRAM范围通过原有镜像检查器；ELF没有Flash写入函数。RAM报告中的program_excludes_logs_and_filesystem=false表示该字段只用于Flash程序布局判断，不表示RAM镜像覆盖了Flash。

Flash程序及其4KiB擦除对齐范围均在第一个日志区0xe0000之前；两个日志区为0xe0000/0xf0000、每区65536字节，文件系统起点0x100000。Flash镜像本身含运行期日志写入功能，程序区避让不能等同于运行时没有Flash写入。

两种ELF静态区均低于HeapLimit，链接未溢出。这里只证明静态布局，不证明动态堆/栈高水位或运行稳定性。配置为4MiB不等于本次重新测量了实物容量；实物容量来自Windows既有验证。

机器证据：[MAC_V042_BUILD_VERIFICATION_2026-10-22.json](MAC_V042_BUILD_VERIFICATION_2026-10-22.json)，含镜像/ELF/源码/依赖归档SHA256。所有镜像使用公开example网络参数，只用于编译验证，不能直接用来验证连接。源路径、工具及参数会影响哈希，不要求与Windows镜像相同。

## 复现入口

在仓库根目录，准备同版本SDK及上述依赖；将cmake、ninja、arm-none-eabi-gcc和arm-none-eabi-nm放入PATH。设置PICO_SDK_PATH；如单独安装picotool，picotool_DIR指向含picotoolConfig.cmake的目录。此次路径是build/tooling/picotool-install/lib/cmake/picotool。

```sh
export PATH="$PWD/build/tooling/venv/bin:$PWD/build/tooling/arm-gnu-toolchain-14.2.rel1-darwin-arm64-arm-none-eabi/bin:$PATH"
export PICO_SDK_PATH="$PWD/build/tooling/pico-sdk-2.3.1"
export picotool_DIR="$PWD/build/tooling/picotool-install/lib/cmake/picotool"
python3 tools/build_pico_snapshot.py --variant v042 --profile ram --compile-only
python3 tools/build_pico_snapshot.py --variant v042 --profile flash --compile-only
```

新增--compile-only会把公开example头文件写入build/compile-only-private，并使用独立的*-compile-only构建目录，不读取或覆盖work/private真实凭据。入口仍无烧写操作；RAM另加nm符号检查。构建日志位于build/tooling/v042-ram.log和v042-flash.log。

准备picotool时可按官方BUILDING.md配置，额外传入-DPICOTOOL_NO_LIBUSB=1。SDK的自动Git下载在本机失败，改用官方固定tag归档构建并显式传picotool_DIR后成功；Python下载的证书配置异常通过系统curl正常TLS校验绕开，没有关闭证书校验。

## 尚未完成

v042 Flash实机烧写/运行、持久日志END2、真实游戏输入震动闭环、Windows重构后的完整父子进程/HID/计时器/网络回归均未验证。此次编译成功不能替代这些验收。硬件测试暂停继续有效。跨机接续见 [最新Windows交接](WINDOWS_RESUME_2026-10-22.md)。
