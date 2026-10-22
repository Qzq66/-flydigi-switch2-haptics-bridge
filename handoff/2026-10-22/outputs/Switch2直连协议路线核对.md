> 历史阶段记录；当前状态以仓库 docs/HANDOFF_2026-10-22.md 和 docs/STATUS.md 为准。路径及设备序号已脱敏。

# Switch 2直连协议路线核对

检索日期：2026-10-22。下述为公开文档及作者报告，不是本项目Switch 2实机验证。

## 目前决策

优先将一代Pro协议作为首次USB识别及基础HD Rumble数据接收的候选路径，同时继续研究Switch 2 Pro原生协议。先证明主机实际发来的数据，再决定是否需要原生协议；不能把一代HD Rumble兼容路径称为HD Rumble 2完整还原。

| 路线 | 公开证据 | 本项目适用范围 |
| --- | --- | --- |
| 一代Pro兼容 | Pico-DualSense-Switch-Bridge作者声明Switch 2兼容，使用057E:2009和一代Pro协议，按键和基础震动已验证，HD震动翻译仍为实验状态 | 适合参考枚举、握手与震动数据入口；需补齐描述符、虚拟校准和主机请求应答 |
| Switch 2 Pro原生 | ndeadly公开了057E:2069的描述符、初始化和输入/输出报文 | 新协议研究资料已存在；尚不能据此断定完整仿真简单或不需要额外校验 |
| 商用品Switch 2支持 | 八位堂官方固件记录列有多个型号新增Switch 2支持 | 证明用户所说的商用兼容路径存在；未公开其完整线协议，不能据此推断都使用同一种新协议 |

## 协议差异的实现影响

一代Pro实验部分已在电脑端验证0x80握手、0x21子命令应答、0x30中性输入及8字节震动字段接收。当前实验USB身份为CAFE:4010，虚拟读取只返回FF，尚未实现真正的主机兼容描述符和校准，不能移到Switch 2进行有效识别测试。

Switch 2 Pro研究文档列出新输入0x09和输出0x02；左右触觉数据各有16字节区域。公开USB描述符包含HID、厂商Bulk及耳机音频相关接口，不能仅替换VID/PID就视为完成原生Pro仿真。音频接口的存在也不能说明触觉就是直接PCM音频。

Linux Switch 2研究可作为打包振动格式及传输参考，但其协议说明主要聚焦Joy-Con 2，驱动主机端能驱动真手柄，也不自动证明设备端能被Switch 2认可。资料中的主机调度策略、幅度限制与真正线协议要分开。

## 后续具体缺口

1. 参考已有一代Pro实现补齐描述符、握手状态、校准和初始化应答，继续先在电脑测试。
2. 为Pico从电脑移到Switch 2后采集命令和震动建立日志通路；当前RAM镜像拔电即消失，直接换线不能保留它。若需要持久写入Pico，先说明并保留原固件备份及恢复步骤。
3. 真机测试前说明自制USB设备尚无零封禁风险保证；离线测试不是防封承诺。不开启升级、擦写、NFC、配对密钥或绕过主机保护功能。
4. 捕获原始震动数据后，再解码并接入已验证的飞智低幅度输出路径。接收器继续在电脑侧，尚未完成Pico到电脑的数据回传，不能只靠一个USB集线器把两台主机连通。

## 来源

- Pico同类桥接及限制：https://github.com/thsrhwk01/Pico-DualSense-Switch-Bridge
- 原生协议研究：https://github.com/ndeadly/switch2_controller_research
- 原生描述符：https://github.com/ndeadly/switch2_controller_research/blob/master/descriptors.md
- 原生报文：https://github.com/ndeadly/switch2_controller_research/blob/master/hid_reports.md
- 原生命令：https://github.com/ndeadly/switch2_controller_research/blob/master/commands.md
- Linux主机实现及协议说明：https://github.com/novakpetya/linux-switch2/blob/main/PROTOCOL.md
- 商用固件记录：https://support.8bitdo.com/

风险资料记录：用户提供社区帖子作为经验参考。其中“只要不用烧录卡就没有ban机风险”没有足够证据支持，不能作普遍保证；官方宽泛限制条款也不能直接证明本项目USB手柄会被封禁。未将帖子中的账号、存档、破解系统描述作为已验证事实。
