# Windows 接续说明

## 当前项目是什么

目标是八爪鱼 6 Pro 操作 Switch 2 真机原生游戏，并获得来自游戏原生触觉指令的反馈。不是在 PC 运行 Switch 游戏，也不是从游戏混音生成震动。

现已完成 Mac 接收器枚举和厂商身份／状态查询，详见 `docs/MAC_RECEIVER_DIAGNOSIS.md`。接收器为 `37d7:2502`，设备类型 `0x96` 对应八爪鱼 6 Pro；第三方接管许可字段为 0。按键流、震动输出、Pico 固件和 Switch 2 兼容均未验证。

后续以 Windows 为主开发与硬件实测环境，Mac 负责资料、审阅及文档。Windows 是开发测试台，最终独立桥接器不依赖 Windows。参见 `docs/CROSS_PLATFORM_WORKFLOW.md`。

## 同步到 Windows

安装 Git for Windows 后，通过 GitHub Desktop 克隆目标仓库，或在 PowerShell 使用仓库页面提供的 HTTPS clone 地址：

```powershell
git clone https://github.com/Qzq66/-flydigi-switch2-haptics-bridge.git flydigi-switch2-haptics-bridge
Set-Location flydigi-switch2-haptics-bridge
git status
```

远程仓库名称以一个连字符开头，本地目录名已改为不带该前缀的名称。若日后改成私有仓库，使用 GitHub 登录流程，不将 token 写入命令或文件。

之后每次开始工作，先检查本地改动，再拉取更新：

```powershell
git status
git pull --ff-only
```

存在未提交改动时，先妥善提交或保留，不使用强制重置。macOS 和 Windows 不要同时修改、推送同一工作分支；分支默认用 `codex/` 前缀。另一台电脑开始前先确认上一台的提交已经推送。

## Windows 下一次工作的顺序

1. 阅读 `开发计划.md` 和 `docs/STATUS.md`。
2. 确认硬件是否到货、八爪鱼及原装接收器是否齐全，记录现有固件版本。
3. 盘点已有 Git、CMake、编译器、Pico SDK 和调试工具，避免盲目重复安装。
   - 先阅读 `docs/FLYDIGI_OFFICIAL_FINDINGS.md`；在飞智空间站高级设置检查“允许第三方应用接管映射”。开启会停用飞智自身映射服务，记录前后状态，不与原生触觉基线的设置混淆。
   - 手柄电量保持高于 20%。按键、普通震动、原生音圈输出分别验证。
4. 阅读 ApexSenseBridge 的 6 Pro 初始化、能力查询、波形打包、发送和停止路径，核对许可证。
5. 有真实八爪鱼时，先按项目发布说明建立 Windows 原生触觉基线，记录实测结果。
6. 提取最小波形输出实验；板卡到货后再验证 USB 设备端与工具链。

现阶段不要直接启动完整固件集成，不假设蓝牙能输出音圈 PCM，也不要承诺 NS2 Pro 已能被主机识别。

## 关键事实和限制

- 买的是第三方 Type-C Pico 2W，商家参数表标称 2 MB Flash。无线芯片、USB 布线和 SDK 兼容性待确认。
- 一根 Type-C 数据线并不证明板卡支持所需桥接功能。
- Pico 原生 USB 控制器只有一个。面向主机的设备端和面向手柄的主机端不能共用这一控制器同时工作。
- PIO USB 是待评估方案，接收器端点、速度与厂商命令需先检查。
- ApexSenseBridge 的 Windows 驱动／EXE 不能直接运行在 Pico；需要移植协议和纯处理逻辑。
- VIIPER 的 PC 虚拟 NS2 Pro 不等于真机设备端模拟已成功。
- NS2 已知参数布局并不证明所有震动模式、标志和多帧时序完整可用。
- 第一个真机原型可由电脑负责转换，电脑不运行游戏；Pico 与电脑调试通信使用独立链路。

## 可直接交给 Windows 上开发助手的任务

> 请继续本仓库的八爪鱼 6 Pro → Switch 2 真机原生触觉桥接项目。先检查 Git 状态，拉取远程更新，再读 README.md、开发计划.md、docs/STATUS.md、docs/WINDOWS_HANDOFF.md、docs/MAC_RECEIVER_DIAGNOSIS.md 和 docs/FLYDIGI_OFFICIAL_FINDINGS.md。Mac 已验证接收器枚举、身份与状态查询，接管许可字段为 0；按键流、震动输出及固件尚未验证。以 Windows 为主要硬件测试环境，先盘点工具链、硬件和固件，检查第三方接管开关及手柄电量，再核查 ApexSenseBridge 输出接口和许可证，建立最小左右独立波形测试。不要将普通震动视为原生波形，也不要将 PC 识别视为真机兼容。结束时更新 STATUS.md 的验证、问题和下一步，提交并推送本次修改；有冲突时保留双方改动，不强制覆盖。

## 每次交接记录

在 `docs/STATUS.md` 记录日期、当前分支／提交、硬件及软件版本、实际完成的验证、失败现象、待处理项和下一步。原始抓包需筛查身份信息后再决定是否上传。
