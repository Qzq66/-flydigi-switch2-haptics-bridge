# 脱离电脑主线：2026-11-15

用户再次明确：最终产品必须无需电脑运行。此前电脑回放仅是协议与波形验证工具，不应继续作为交付主线。暂停增加电脑自旋、幅度阶梯或重复游戏试次；现有证据保留。当前只做离线准备，未获得新的接线、烧写或主机试次授权。

目标数据路径：Switch 2 → Pico 原生USB设备端 → 板上输入/震动处理 → 独立USB主机端 → 飞智原装接收器 → 手柄。电脑仅用于开发、编译及可选诊断，运行验收必须拔除电脑且不依赖其热点/转发。

## 已核实的缺口

| 部分 | 当前证据 | 脱机所需工作 |
| --- | --- | --- |
| 主机侧兼容输入/震动接收 | v043 `main.c:107` 有主机HID接收回调，`:260` 主循环执行 tud_task 和 bridge_poll | 复用已验证设备端，改成板内数据路由；不是完整NS2 Pro/HD Rumble 2已完成 |
| 第二条USB路径 | v043 `CMakeLists.txt:27` 只链接 tinyusb_device；`tusb_config.h:3` 只启用 CFG_TUD_ENABLED | 增加并验证独立USB Host路径；集线器本身不能补足主机控制器 |
| 飞智输入 | `handoff/2026-10-22/work/bridge_windows.py:30` 的 XInputSource 依赖Windows | 从接收器真实USB输入报告读出按键/摇杆；不可把XInput结构当作线上USB报文 |
| 波形输出 | `docs/PROTOCOL_NOTES_2026-10-22.md:9` 有0x57波形及已知临时模式协议，`:13` 记录Windows报告ID语义 | 板上USB传输适配和停止确认；Windows 33字节缓冲不能直接假定为线上包长 |
| 解码与保护 | Python归档双频字段和独立PCM复算已通过软件验证 | 移植为板上定时处理，用原始字段/PCM参考向量核对，不把电脑调度通过当固件通过 |

原决策已见 `开发计划.md:19`（单原生控制器）、`:29`（PIO USB候选）、`:31`（双MCU备用）。重新聚焦这些未完成项。

## 优先路线与待证实条件

优先离线评估现有Pico的PIO USB Host，不先购买板子。上游项目 [Pico-PIO-USB](https://github.com/sekigon-gonnoc/Pico-PIO-USB) 在2026-11-15检索时声明支持RP2040/RP2350；[Raspberry Pi host示例配置](https://github.com/raspberrypi/pico-examples/blob/master/usb/host/host_cdc_msc_hid/tusb_config.h) 提供PIO主机配置入口。这些是选型依据，不是此第三方板、复合接收器、输入接口或厂商输出兼容性的证据。依赖版本、接收器速度/接口/端点、引脚、电源及并行设备端运行均待核对。

特别约束：现有v043 `CMakeLists.txt:28` 注明core1从未启动，`:29` 据此配置PICO_FLASH_ASSUME_CORE1_SAFE。若新USB主机实现使用第二核心，不能沿用这个假设继续写Flash日志；新目标应与旧固件隔离，先完成RAM/不写Flash日志的设计审查。当前不刷写，不启动第二核心。

## 从现在开始的里程碑

1. **USB接收器可移植性闸门**：先从已保存证据定位真实描述符、速度、端点、输入报告及厂商输出路径，明确哪些只有Windows抽象。离线固定依赖和编译独立枚举/只读输入探针；证据不足则指出缺失项。需要现场时只申请一次有明确目的的枚举/输入验证，未通过不叠加震动。
2. **板上接收器输入**：按键、摇杆映射不依赖XInput，离线用真实USB报告向量核对，再独立验证输入。PIO不兼容时依据失败原因选双MCU/独立USB控制器，不反复在同一未知接口上试振动。
3. **板上解码及波形输出**：把已知命令打包、双频解码/合成迁入独立C/C++目标；与归档参考逐字段、逐PCM样本比较。持久配置命令禁止，保留既有幅度/能量/时序/停止保护。脱机源有效性和断流计时依据需明确设计，不静默删除80ms保护。
4. **无电脑闭环**：同一硬件同时维持主机输入与接收器通信；拔掉电脑、不使用电脑热点，真实游戏可操作、有源震动且及时停止。断线、重连和供电恢复无自动重播；保护失败不能以主观有震动代替通过。

本阶段交付是路线核对，尚无脱机固件可用。此前2～4周/1～2个月估算缺少接收器Host兼容性依据，撤回为可靠工期预测；先关闭第1项不确定性再估算剩余工作。后续只为能推进上述里程碑的缺口增加测试。
## 本轮补充：烧录授权与单C口限制

用户已允许为接收用途烧录Pico，当前尚未执行，也没有准备好完整接收固件。用户指出板子只有一个C口；现有GPIO PIO Host方案需要额外USB接口及供电/接线设计，不能把原C口经普通Hub同时当作主机端和设备端。外接原装接收器是否可接受仍待确定；直接无线接手柄的蓝牙输入与精细震动通道也未确认。已完成只读USB输入组件静态交叉编译，见 `../standalone/receiver_probe/README.md`；它不是可烧固件，不等于蓝牙接收实现。
## DS5Dongle参考后的优先级更新

用户提供DS5Dongle发布例子。已核对v0.8.0及提交77d378effcda11abee87f9be1ac31d6518e87560：Pico2W原生USB设备端与CYW43经典蓝牙可以并行，不要求第二个USB口。此前“优先PIO USB原装接收器”的决定调整为备用路线；优先做飞智蓝牙发现/只读输入可行性验证。单个C口本身不是蓝牙桥接障碍。

详见 `DS5DONGLE_REFERENCE_2026-11-15.md`。Sony专用识别、描述符和触觉报告不能直接当飞智协议；飞智蓝牙输入/精细震动仍未验证。没有下载/烧写原版UF2，没有运行会切换SDK的上游构建脚本。用户的烧录授权保留，不重复索取；本轮只完成参考核对。
## 第二份无线触觉参考：PRO2 Bridge v2.9

用户补充NS2 Pro BLE连接PC并转译PS5触觉的项目。已绑定pro2-v2.9提交ed148a9462d6f65946b737ee8c879d17e41f581b核对，见 `docs/PRO2_BRIDGE_REFERENCE_2026-11-15.md` 及 `pro2-bridge-reference.json`。它采用BLE/GATT，PS5 PCM经有损双频参数提取后编码为NS2 Pro专用33字节包；原生参数转发另有路径。频率映射明确未物理标定，输出队列也明确不是播放保证。不能把任天堂BLE格式直接套给飞智，也不能把仓库历史“USB Pro2输入→无线模拟手柄、仅普通震动”的Pico固件当成目标固件。

两份参考继续支持“单Pico USB设备端 + 蓝牙”作为优先可行性方向。下一项仍是飞智实际蓝牙服务/输入识别与独立输出协议闸门，不增加PC自旋/震动回放。未下载/运行EXE，未烧写或改设备设置。
## APEXtoDS与三份参考的集成路线

本次只读检查 `D:/下载/APEXtoDS/APEXtoDS-0.8.25.10-Windows-x64/APEXtoDS`。EXE、APEXMaestro.dll、BUILD-INFO、许可、便携说明与用户手册共6文件的SHA256均符合随包清单；这只确认包内一致，不证明运行效果或发布者身份。未运行、反编译、复制二进制，未改设备。

便携说明第8行只列USB线/无线接收器，13行说明私有HID唯一输入；用户手册第588行明确不把蓝牙列为已验证方式。分发包未见APEX核心的可移植源码，MSVC x64 EXE/DLL不能作为Pico固件模块。文档要求最低固件9.0.7.6仅是该程序的条件，本次没有查询或升级手柄，也不会将其自动替代本工程已验证基准。

### 推荐按模块组合

| 模块 | 采用/参考来源 | 已知边界 |
| --- | --- | --- |
| 面向Switch的USB设备身份、输入报告与主机震动接收 | 现有v043及已保存真机证据 | 一代Pro兼容端；完整NS2 Pro身份/HD Rumble 2尚未完成 |
| 单板USB设备端与CYW43蓝牙协同 | DS5Dongle | Sony专用过滤/报告须替换，Classic与BLE须按飞智实际模式确定 |
| 蓝牙触觉通道设计、设备发现及参数/传输分层 | PRO2 Bridge v2.9 | NS2 Pro的BLE UUID、初始化及包格式不能用于飞智；PCM转换有损 |
| 飞智输入与触觉体验参照 | 本地APEXtoDS | 本包仅有Windows产品，不能直接编译进Pico，未证明蓝牙细致触觉 |
| 飞智波形打包的公开实现 | ApexSenseBridge `src/flydigi/Apex6Protocol.h/.cpp` | USB/接收器协议参照，不是飞智蓝牙通道的证明 |

公开ApexSenseBridge本次绑定提交 `f43d06a828a78c709bf336bcd7f93beb026ba3c0`。其头文件`:14`至`:21`定义32字节私有帧、33字节Windows报告与0x57实时命令，`:47`至`:55`定义每包8组trigger/leftGrip/rightGrip样本；实现`:155`至`:174`负责实时波形封装。这与本项目已验证输出形态相符，可作为独立固件移植的公开对照，不需要从本地APEXtoDS二进制提取源码。仅选择已知波形/身份部分，不照搬配置槽、灯光等无关写入。

参考：[飞智协议头](https://github.com/ReynArts/ApexSenseBridge/blob/f43d06a828a78c709bf336bcd7f93beb026ba3c0/src/flydigi/Apex6Protocol.h)、[波形打包](https://github.com/ReynArts/ApexSenseBridge/blob/f43d06a828a78c709bf336bcd7f93beb026ba3c0/src/flydigi/Apex6Protocol.cpp)。

拟实现的运行通路：

`Switch 2 USB → Pico接收主机震动参数 → 板上双频/波形处理 → 飞智蓝牙输出适配（未验证）→ 手柄`

输入方向反向：

`飞智蓝牙输入报告（未验证）→ Pico按键/摇杆解析 → 现有Switch兼容USB输入报告 → Switch 2`

不在中间额外模拟PS5身份。APEXtoDS与PRO2助手都是为PC游戏提供虚拟手柄、再把反馈发给各自实体设备；不是可在无电脑条件下首尾衔接的通用转换程序。对本项目也不必加入PS5 PCM频谱提取，因为上游已经提供震动参数。电脑端虚拟USB、驱动和界面不属于运行时链路。

### 尚未连通的唯一设备协议段与下一步

当前缺口集中在飞智蓝牙端：需要识别Classic HID/BLE/其他服务、读取真实输入报告，并找到被手柄实际接受的精细波形输出格式。USB 0x57能工作、不等于同一包能直接写入蓝牙；PS5/NS2 Pro蓝牙能震，也不等于飞智实现相同通道。

下一项仍先制作独立发现/只读输入候选，再验证具体输出能力；不能以“发现/配对成功”代替震动协议通过。若蓝牙不开放所需触觉，只能据实选择原装接收器+独立USB Host的备用硬件路径，或明确降低震动目标，不能靠串联上述软件绕过缺失的手柄固件接口。

结论：模块组合路径清楚，现有证据尚不足以宣称“单个Pico直接无线接飞智且精细震动”已经可用。详证据见 `campaigns/realtime-2026-11-15/apeXtods-integration-review.json`。本轮无硬件操作，不增加Windows性能或游戏回放试次。
## 用户提供的ApexSenseBridge源码地址已确认

用户明确提供 https://github.com/ReynArts/ApexSenseBridge 。已确认公开的 `Apex6Protocol.h/.cpp`（身份/波形协议）、`Apex5Input.cpp`（私有输入解析）、`Apex6HapticBridge.cpp`（触觉处理），以及需要替换的Windows传输实现。核对提交f43d06a828a78c709bf336bcd7f93beb026ba3c0，见 `apexsensebridge-source-confirmation.json`。

澄清：此前“本地APEXtoDS包无核心源码”只描述检查过的分发包；不能推断同功能的公开项目没有源码，也未证明本地APEXtoDS二进制来自ApexSenseBridge。该公开项目是可用的协议研究参考。当前支持表仍只列USB/原装接收器，不证明飞智蓝牙波形通道。该提交README写MIT、LICENSE文件写GPL-3.0-or-later，存在标记差异，本次未复制整合源码或据此作许可结论。

未操作硬件、未烧录、未运行二进制。继续以单Pico蓝牙接收可行性为主线，不增加电脑回放试次。

## 第一项：蓝牙发现探针离线就绪（尚未现场扫描）

`standalone/bt_discovery/` 已生成仅在RAM运行的Classic查询/BLE被动扫描探针；USB仅串口，不含键鼠模拟。SDK蓝牙TLV存储已替换为RAM，最终ELF未发现Flash擦写函数。镜像总计357304字节，日志解析8项测试通过。原SDK、Pico和手柄均未改动，用户选择本轮只保存离线成果。

详见 [探针说明](../standalone/bt_discovery/README.md) 与 [构建证据](campaigns/realtime-2026-11-15/bt-discovery-offline.json)。下一步是实际BOOTSEL/Flash只读预检后做一次RAM扫描；完整SDP/GATT服务、输入报告及精细震动仍未验证。扫描不连接、不配对，不代表已经打通蓝牙接收器。

## 2026-11-16：三个项目按角色重新组合

用户指出NS2 Pro可以模拟DS5，这正是跨品牌转换可行的证据。桥接层负责身份和协议转换，实体手柄只需理解自己的协议，不能误读为“飞智必须原生支持Sony格式”。同时，转换可行不代表任意传输口都开放等价触觉能力。

| 项目 | 主机看到的设备 | 真实手柄与反馈目的地 | 本项目复用点 |
|---|---|---|---|
| DS5Dongle | Pico模拟的有线DualSense | 蓝牙DualSense，反馈重新封装成Sony蓝牙格式 | 单Pico的USB设备端+蓝牙Host并行、缓冲与连接框架 |
| XinHeLianSheng Pro2 Bridge | Windows虚拟DS5/其他身份 | 实体NS2 Pro，DS5反馈转换为NS2 Pro输出，支持BLE路径 | 将虚拟身份、输入映射、触觉表示、实体协议编码分离的架构；任天堂马达参数格式参考 |
| ApexSenseBridge / 本地APEXtoDS用途 | 虚拟DS5 | 实体飞智，DS5触觉转换为飞智波形；已核对公开项目的APEX6Pro支持为USB/接收器 | 飞智波形编码与触觉处理；Windows传输后端须替换 |

目标链路为“Switch USB兼容身份 ↔ Pico上的输入/触觉转换 ↔ 飞智蓝牙协议 ↔ 实体飞智”。主机面向Pico发送任天堂反馈，不必要求飞智理解任天堂原包。可复用触觉中间表示/渲染算法；PC虚拟DS5身份只是以上Windows项目接收PC游戏反馈的入口，不是本项目运行时必须插入的一层。

PRO2源码中的PS5 PCM→任天堂双频参数是一个转换方向，不能直接倒过来就宣称得到任天堂→DS5的无损转换。若借用DS5 PCM作中间表示，需新增任天堂参数合成波形和飞智渲染；是否划算要以保留语义、算力和时序为依据。主机已经给出频率/幅度参数时，优先直接转换到飞智执行器样本，避免额外有损分析。

当前应分开描述：①单Pico桥接架构已有公开示例；②任天堂/DS5/飞智跨品牌触觉转换已有相关实现；③飞智蓝牙通道的连接与输出能力尚缺证据。Windows已确认目标Classic HID服务和正常输入；Pico的v7认证仍失败，细节见 [配对记录](BT_PAIRING_REQUIREMENTS_2026-11-16.md)。前期经电脑+接收器的游戏闭环不等同于纯Pico脱机已完成。

下一步优先结合DS5Dongle真实蓝牙Host初始化/配对流程，与本机BTstack设置逐项核对，输入连接与触觉移植可分开推进。Windows抓包是可选诊断手段，当前用户明确暂不UAC，保持暂停，不作为完成整个离线模块设计的前置门槛。不改变现有保护，不自动追加硬件试次。

参考：[DS5Dongle](https://github.com/awalol/DS5Dongle)、[PRO2 Bridge](https://github.com/LeonChrome/XinHeLianSheng-Pro2-Bridge)、[ApexSenseBridge](https://github.com/ReynArts/ApexSenseBridge)。PRO2详细源码结论仍绑定此前v2.9审阅，不将当前滚动首页新版本功能混入该冻结证据。

### 补充：第三方Switch模式是应优先核对的协议入口

用户补充第三方手柄常有Switch模式，部分产品采用自研线性/音圈执行器并宣称复现HD震动。这是重要路线线索：实体手柄固件可以自行接收任天堂反馈并驱动本厂执行器，Pico不一定要走XInput再自行重建全部波形。不能将“有Switch模式”“有音圈马达”“接受HD参数”“体感等同原装HD/HD Rumble 2”四件事合并认定；具体型号和固件分别验收，不泛称所有第三方都有或都完美。

已核对[飞智官方Connection Guide](https://flydigiglobal.helplook.com/docs/Connection-Guide#Nintendo-Switch)：明确提供Mode Switch → Switch，无线在Change Grip/Order登记，USB使用Pro Controller Wired Communication。它证明存在Switch输入连接模式，未在该页证明APEX 6 Pro HD/HD Rumble 2保真能力。没有执行其重置/清除配对操作，也未实际切换模式。

新增优先分支：检查飞智Switch模式的身份、配对与HID描述符、初始化及输出报告；若它接收同一代任天堂震动编码，可优先在Pico做封装/时序转换或受控转发，把驱动执行器交给飞智原固件。是否可直接转发必须以实际报告布局和初始化要求验证，不能把Switch一代HD报文直接等同Switch 2 HD Rumble 2。

这条路径与XInput蓝牙协议不同，应在继续深入XInput抓包前离线核对现成Nintendo HID Host实现及飞智官方模式资料；可能减少私有触觉协议逆向，但不会自动解决该模式的实际连接及HD能力。用户目前要求补充路线，未授权本轮实际切模式/配对/主机测试；本轮仅更新研究依据，原UAC采集保持暂停。

### 通用Switch Host离线核对已完成

根据用户进一步澄清，研究范围以第三方通用Switch模式为主，飞智仅作为实际适配对象。已核对Bluepad32固定提交的标准报告、第三方SDP兼容分支和初始化流程。其高层震动API固定150Hz且两侧复制同一数据，不能直接当HD保真层；其自动确认及短密钥策略不自动照搬。没有操作硬件或集成上游代码。详见 [通用Switch Host核对](SWITCH_HOST_REFERENCE_2026-11-16.md)。下一项为通用Switch模式RAM输入探针，先确认目标身份与输入，再验证实际震动参数支持。
