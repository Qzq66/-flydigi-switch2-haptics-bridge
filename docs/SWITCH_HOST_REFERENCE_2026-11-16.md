# 通用第三方Switch模式：Host实现离线核对

结论：已有Nintendo HID Host和第三方兼容参考，应优先复用标准协议及兼容分支，不将研究限定为飞智专有协议。本轮未切换模式、连接设备、刷固件或发送初始化/震动命令。

## 固定源码

Bluepad32提交`80d6314e46f871719fbb4b721a2cc02227c4f369`。只读取得`src/components/bluepad32/parser/uni_hid_parser_switch.c`、`src/components/bluepad32/bt/uni_bt_bredr.c`、LICENSE。GitHub匿名API首次限流，随后通过GitHub连接器核对提交，再读取固定提交原文；失败的空提交manifest保留，不能拿它作来源。文件哈希见 [证据](campaigns/realtime-2026-11-15/switch-host-reference-20261116.json)。未运行上游脚本或复制进产品代码。

## 可复用的协议事实

下表行号均针对上述固定提交，而非滚动main。

| 模块 | 实现位置 | 可以借用什么 |
|---|---|---|
| Classic HID控制/中断通道 | uni_bt_bredr.c:34、45 | 复用BR/EDR Host及L2CAP通道设计 |
| 部分兼容手柄的SDP绕行 | uni_hid_parser_switch.c:1333；uni_bt_bredr.c:224 | 上游识别已知名称后可省略SDP，说明SDP不响应不等于不能使用；本项目仍需人工确认模式和锁定目标，不能按名字自动连接任意外设 |
| 输入报告 | uni_hid_parser_switch.c:96、898、1042 | 0x21为子命令应答，0x30为完整输入，0x3F为基础输入；映射与长度校验可参考 |
| 兼容手柄校准 | uni_hid_parser_switch.c:859 | 处理第三方全零校准数据，避免直接套原装假设 |
| Host输出封装 | uni_hid_parser_switch.c:168、1381 | HID Data/Output头、0x01子命令／0x10纯震动、4bit包序号、左右各4字节震动区 |
| 最小初始化参考 | uni_hid_parser_switch.c:1115、1199 | 设备信息请求0x02，设置报告模式0x03→0x30 |
| 可选功能 | uni_hid_parser_switch.c:1211、1223 | IMU开关0x40、震动启用0x48；不应在首个只读输入探针自动开启 |
| 停止编码 | uni_hid_parser_switch.c:1409 | 两侧中性编码00 01 40 40；仅作为协议参考，具体设备执行仍须验证 |

标准Switch模式与XInput模式可以是不同的固件接口；第三方可能采用同一任天堂报文，也可能只实现子集。不能由Switch兼容、音圈执行器或USB包长度推断完整HD保真。主机兼容身份也不等于Switch 2原生HD Rumble 2身份。

## 不照搬的部分

- `uni_hid_parser_switch.c:1281`把频率固定150Hz，`:1434`把同一震动数据复制到两侧。该双强度API不适合直接承载我们的左右独立、随时间变化的原始HD参数。保留原报文有效载荷、重封装包序号与传输头是候选，但必须先验证真实布局；不同代协议不盲转。
- 上游完整初始化会读校准、启用IMU/震动、设置LED，并含调试Flash dump路径。只选择必要阶段；不把SPI读取误称写入，也不执行Flash写、配对清除或配置命令。
- `uni_bt_bredr.c:151`开启SSP自动确认；`:154`至`:157`将最小加密密钥长度设为7。当前项目不自动接受确认或降低密钥长度，不能因上游这样做就照抄。上游策略差异仅作为兼容性线索，非当前认证失败根因证据。
- Bluepad32本体Apache-2.0；LICENSE同时指出依赖BTstack存在单独商业/开源授权条件，移植应分别核对并保留许可。

## 下一项明确交付

准备通用Switch模式的RAM输入探针，先发现并锁定用户指定目标，检查Classic连接、报告ID及按键变化。不能沿用XInput模式的地址和身份而不重新确认。第一阶段不启用震动；必要的报告模式请求独立人工启动，附两侧中性震动区。若第三方不回应SDP，比较已知Switch名称与通道直接连接分支，保留失败上下文，不自动轮试。

连接/输入通过后，才在同频变幅和同幅变频的受限输出里区分“仅强弱映射”与“设备接受频率参数”；能感觉到差异也不等于原装HD/HD Rumble 2保真。此前已有电脑端频率/幅度体感证据不重做；这里需要验证的是新的Switch模式通道。

官方资料只作为设备边界补充：[飞智连接指南](https://flydigiglobal.helplook.com/docs/Connection-Guide)确认存在Switch模式，但未提供该型号HD保真承诺。通用实现参考：[Bluepad32固定Switch驱动](https://github.com/ricardoquesada/bluepad32/blob/80d6314e46f871719fbb4b721a2cc02227c4f369/src/components/bluepad32/parser/uni_hid_parser_switch.c)、[Classic Host](https://github.com/ricardoquesada/bluepad32/blob/80d6314e46f871719fbb4b721a2cc02227c4f369/src/components/bluepad32/bt/uni_bt_bredr.c)。

## 独立RAM输入观察候选已离线完成

已创建 [switch_input_probe](../standalone/switch_input_probe/README.md)，未复制上游代码或修改现有XInput探针。标准Classic HID通道直接连接、显式目标锁定、人工15秒输入采样已编译；初版不发任何HID输出或初始化命令，不启用震动/IMU/LED。没有收到输入时不能冒充按键验证通过。

镜像总占用373776字节，全部LOAD内存段在RP2350 SRAM；Flash擦写及HID输出直接调用为0，应用对象也不导入L2CAP数据发送接口。首个现场入口`work/switch_discovery_probe.ps1`只做一次发现，带完整Flash前后核对及verify，等待确认Switch模式的新身份后才另做连接。配置、编译、调用审计和脚本语法检查通过，尚未加载设备或运行时测试。[离线证据](campaigns/realtime-2026-11-15/switch-input-probe-offline-20261116.json)。

## 首轮发现已执行：目标尚未找到

用户确认Switch配对准备后执行一次发现，记录RADIO_READY及discovery_complete_no_connection。只观察到1条无名称设备，CoD=0x2e410c，其major class不是外围游戏手柄；未观察到旧XInput地址，也未获得可确认的Switch模式目标。不据此断言该模式不使用Classic或不受支持，不将“采集完成”计为“目标发现通过”。

前后完整4 MiB Flash哈希一致、physical verify通过，RAM错误0，输入报告0、Output报告0，没有连接或配对，Pico已回BOOTSEL。见 [首轮现场记录](campaigns/realtime-2026-11-15/switch-discovery-field-20261116-124543.json)。

没有自动重扫。先询问用户屏幕实际为Switch配对中、连接中还是已连接。本探针未显式开启RSSI/EIR inquiry，名字缺失不是排除设备的依据；下次候选应补齐扩展查询/必要的远端名称获取，但不能据此宣称本次未找到目标的根因已确认。仍需确保模式身份、广播/查询时段和实际可发现状态，不复用XInput地址或连接此未知设备。

## 用户纠正连接对象；后续入口已准备

用户随后明确说明：手柄此前误连NS2主机，当前已断开与主机的连接。此前“已连Pico／可电脑测试”的表述不作为连接证据。只读电脑检查时Pico实际为BOOTSEL，WinMM未枚举到可用手柄；未加载新固件或启动按键窗口、未发送震动。`tools/check_switch_windows_input.py`仅作了只读inventory，结果为空，不能判定模式不受支持，也没有实际按键试次。

已编译v2发现候选，新增显式RSSI/EIR inquiry和版本标识；只查设备，不连接、不配对、不发Output。入口`work/switch_discovery_eir_probe.ps1`语法与镜像调用检查通过，未加载。[离线证据](campaigns/realtime-2026-11-15/switch-discovery-eir-offline-20261116.json)。下一轮需Pico电脑BOOTSEL、电脑蓝牙关闭、手柄确实处于Switch配对中且主机不抢连；发现实际目标后才准备连接和输入测试，不跳过身份锁定或复用旧XInput地址。

## v2现场结束与实现错误更正

用户确认配对准备后执行一次v2发现。仍只有同一条无名称、非手柄类别记录；Flash完整前后回读和verify通过，未连接/配对/输出，Pico回BOOTSEL。[现场证据](campaigns/realtime-2026-11-15/switch-eir-discovery-field-20261116-130121.json)。

随后离线检查发现实现错误：固定SDK `hci.c:10445`明确要求`hci_set_inquiry_mode`在power on之前调用；该函数只改初始化变量，真正Write Inquiry Mode在`hci.c:2217`初始化阶段发送。v2把调用放在RADIO_READY之后，因此不能宣称本轮已应用EIR。不能由此结果归因手柄或证明不支持Classic；也不能仅靠改时机保证下一次找到目标。

已修正为v3：设置移至power on之前；捕获Write Inquiry Mode命令完成状态，打印INQUIRY_CONFIG，固件和runner均要求控制器ACK成功才允许查询。没有放宽任何限时或输出保护。入口`work/switch_discovery_confirmed_eir.ps1`；编译、语法和调用审计通过，未加载。[修正证据](campaigns/realtime-2026-11-15/switch-confirmed-eir-offline-20261116.json)。此错误由探针实现造成，已向用户明确说明；保留全部历史试次与证据，不再直接按无信息结果重复扫描。

## v3有效EIR发现结果：Classic目标仍未出现

用户确认设备就绪后执行一次v3查询，收到`INQUIRY_CONFIG status=0x00 requested=eir`，随后RADIO_READY与正常查询完成。仍只发现一台CoD=0x2e410c的非手柄类别设备，这次取得名称；没有可确认的Switch目标。不连接、不配对，输入及Output均0，RAM错误0。完整Flash前后哈希一致、physical verify通过，Pico回BOOTSEL。

见 [v3现场证据](campaigns/realtime-2026-11-15/switch-confirmed-eir-field-20261116-130659.json)。这证明初始化时机修正确实生效，但未解决目标发现。不能把经典查询未发现推广为设备不支持Switch模式；此探针仅Classic，不覆盖BLE或设备可发现状态的全部情况。

下一步停止重复Classic-only查询，优先准备/核对同时覆盖Classic与BLE的发现方案，且EIR必须同样在power on前配置并取得ACK。先明确传输种类与实际模式身份，再选择Nintendo Classic Host或相应BLE分支；不套用XInput地址、厂商UUID或HD报告，也不回到游戏震动测试。尚未准备或执行该新增现场试次。

## 当前成功连接已核实为USB Switch Pro兼容身份

用户进一步说明手柄保持Switch模式并连接电脑、被识别为NS Pro。随后只读PnP核对发现真实Present USB设备`VID_057E&PID_2009`，USB Composite与HIDClass USB输入接口状态OK，另一个USB子节点为Error（尚未读取错误码，不据此判定整个输入通路失败）。原始设备拓扑仅保存在`work/private/nspro-current-20261116-131158/pnp.json`。

这是USB连接的Switch Pro兼容身份，不是Pico蓝牙连接证据；厂商ID/PID与显示名称不证明原装身份或HD能力。Switch模式（协议/身份）与USB/蓝牙（传输）必须分开描述，不能把用户处于Switch模式误解为正在广播蓝牙配对。

因此下一项优先读取现有USB HID描述与输入报告，对照0x30/0x3F及按键摇杆变化，不要求用户切回XInput，不再对现有USB连接做盲目无线查询。先不发Output或Feature命令、不测试震动、不替换驱动。后续单口Pico脱机目标仍为Pico的USB端接主机、无线端接手柄；USB参考能提供协议事实，但无线链路需在实际无线可发现状态下另验，不能从USB成功直接宣称通过。

## USB只读输入已验证：标准0x30布局，A/B与左摇杆匹配

本轮用Windows SetupAPI/HID元数据枚举严格选择USB 057e:2009、UsagePage=1、Usage=4，Product=Pro Controller，Input/Output报告长度均64字节、Feature长度0。先于路径过滤不打开其他设备；元数据句柄desired-access=0，输入句柄仅GENERIC_READ、共享访问。没有WriteFile、HidD_SetOutputReport或Feature输出调用，未发初始化、LED、马达或配置命令，未接触Pico。

手动窗口点击后6秒准备，再采集20秒。用户确认按提示操作。实际收到2001份报告，全部ID=0x30、长度64字节，限量保存423份样本。按Nintendo标准布局解析：A在右侧按钮字节bit3，B为bit2；顺序为全松→A→松开→B→松开→A→松开→B→松开，与提示吻合。

左摇杆12bit两轴分别观察到0..4095；开始中心中位数均2056，末尾均2039，说明有四向移动并回到中心附近。该差值只作为观测指标，不写校准、不设置新死区，不把传感器/时间戳变化误当按键变化。

纯离线解码器`tools/switch_report30.py`已保存，5项测试验证标准样例、独立按钮位、12bit打包边界、长度/ID拒绝和USB填充。并非复算原始HID描述符；本轮取得的是HID能力与输入数据，未取得原始report descriptor。

见 [USB输入现场证据](campaigns/realtime-2026-11-15/switch-usb-input-field-20261116.json)。底层`tools/switch_usb_readonly.py`和交互入口`tools/check_switch_usb_input.py`为Windows接收实现，原始接口路径与样本仅存private。没有进一步读写原厂配置对照，所以结论是“未调用任何设备输出接口”，不宣称已做四区配置前后验收。

这项确认Switch模式USB输入与标准布局兼容，并不证明HD输出或无线Pico已打通。下一步优先离线核对标准0x01/0x10输出封装与该接口能力，再准备受限、人工启动的输出验证；不因有Output长度就直接发送，不回到无信息增益的蓝牙重复发现。

## 标准USB震动候选：尚未播放

通过Windows HIDP缓存能力只读查询，当前设备实际声明Output IDs=0x01/0x10/0x80/0x82，均为UsagePage 0xff00、8bit×63数据字节，加报告ID共64字节。不是仅从总长度猜测0x10存在；未提取原始描述符全文，未打开输出句柄或发送报告。

准备`tools/check_switch_usb_rumble.py`，用户点击后倒计时6秒，先确认目标唯一、输出ID0x10声明和10份0x30中性输入，再尝试一次低幅度120ms左右同时震动。仅允许标准0x10+4bit序号+左右各4字节+零填充。中性00014040；低幅度801ac046依据固定Bluepad32频率/幅度表（160Hz，幅度项80≈0.080，两个频带；不是机械校准值）。未集成或执行上游源码。

不发送0x01初始化、0x48使能、Feature、LED、配置槽或持久化命令。实际未振动时不自动追加使能或提高幅度。首个中性包写入超出4ms即不启用；活动帧最多30个，4ms调度/迟到保护、80ms断流保护保留，结束或异常只做一次中性收尾，不自动重播。Windows定时分辨率的临时申请在finally释放，不提高线程优先级、不引入spin或强杀。

限制：Windows非实时系统和异常驱动不能保证物理停止期限；WriteFile完成不等于控制器ACK。若停止写入失败，窗口明确提示正常关闭手柄。前后读取输入活性，物理触感与停止须由用户另确认。没有读取/比较原厂马达配置，因此不把“没有配置命令”包装为“已做配置前后验收”。

纯离线11项检查通过，包括报文边界、序号/侧别、慢写不启用、取消、迟到不追赶、活动写异常中性收尾及停止失败显式报告。实际Windows输出未验证。计划、当前Output能力和源码哈希见 [待测记录](campaigns/realtime-2026-11-15/switch-usb-rumble-plan-20261116.json)。Pico未参与，无需Flash读写；正式现场先确认Steam/Engine/其他输出程序退出，手柄保持USB Switch模式与全松，不再蓝牙扫描。

## 首次手动启动在输入前检误停，未发送震动

用户点击窗口后程序读取10份中性输入，但旧检查将整个misc字节非零视为按键按下，返回BUTTONS_NOT_RELEASED。该检查在创建Writer/发送任何包之前，因此本轮没有中性包或活动震动输出，也不能算震动能力失败。

只读后测10份及此前中性样本均为right=0、misc=0x80、left=0，四轴2056附近。标准Pro的misc实际按钮只占低6bit；固定上位0x80不是已验证的按键，不能当按下。修正分离misc_active_buttons与misc_status_bits，保留原字节，仍拒绝未知bit6及真实A/B、Home、Plus、L/R等按键，摇杆阈值、强度、120ms、4ms/80ms保护均未改变。

补充回归后19项离线检查通过，当前与此前中性样本均通过正确前检。旧失败完整保留：[前检误停](campaigns/realtime-2026-11-15/switch-usb-rumble-precheck-stop-20261116.json)，下一入口绑定 [r2计划](campaigns/realtime-2026-11-15/switch-usb-rumble-plan-r2-20261116.json)。仍需重新手动点击才可输出，不自动重播；用户约定的一次实际短震动尚未播放。

## 修正前检后的手动试次：首个中性包I/O超时，无非零输出

用户再次点击后，10份真实输入通过前检（misc状态0x80被正确保留为非按键，四轴在中心附近）。run()首个中性包在Windows WriteFile完成等待阶段超过4ms，异常`USB output did not complete within 4ms`，活动帧0，未进入非零输出。中性包是否已送达设备未获确认，不能说“手柄拒绝报告”；也没有控制器ACK可据。

后测10份输入正常，临时时间分辨率已释放。用户反馈没有感觉到或看到保护停止，符合未发送活动帧的程序路径。配置/初始化/Feature命令均0，Pico未访问。没有自动重播、加幅或改时长。[现场证据](campaigns/realtime-2026-11-15/switch-usb-rumble-r2-field-20261116.json)。

当前能确认的是USB输入与报告声明，实际震动能力仍未验证。4ms派发预算和底层USB调用完成延迟是不同测量量；现实现把后者也设成4ms，首次中性包即被拦截。因此下一步先离线检查传输实现与实际USB时序，再设计严格零幅度的传输诊断。不得直接放宽活动输出保护、改用猜测性初始化或据无触感判定不支持HD。

## 派发截止与传输完成已分离（离线）

r2 的失败可以精确复述为：同一段代码把「4 ms 派发截止」和「overlapped WriteFile 完成等待」当成同一个量，`Writer.send` 用 `WaitForSingleObject(event, 4)`，`switch_rumble_trial.write` 又用 `elapsed > PERIOD` 再拦一次，所以第一个冷中性包就以 `USB output did not complete within 4ms` 退出，活动帧为 0。

本轮把两者拆开，纯离线，无设备 I/O：

| 量 | 规则 | 值 |
|---|---|---|
| 派发截止 | `now - due > 4 ms` 即停 | 4 ms |
| 传输完成 | 超过传输上限才停，4–50 ms 之间只记录 | 50 ms |
| 断流 | 相邻派发间隔 > 80 ms 即停 | 80 ms |

- 新增 [switch_usb_timing.py](../tools/switch_usb_timing.py)：`evaluate()` 分别返回 `late_ms` / `io_ms` / `slow_io`，`Stats` 分别统计两族分布；
- 新增 [test_switch_usb_timing.py](../tools/test_switch_usb_timing.py) 9 项：6 ms 完成不中止、60 ms 中止、5 ms 迟到中止、统计不混族、模拟 24 帧各 6 ms 完成仍 0 故障、16 个序号的包两侧恒为中性；
- `Writer.send(packet, timeout_ms=4)` 增加显式上限，默认值不变，旧路径行为不动；
- 新增 [switch_usb_timing_probe.py](../tools/switch_usb_timing_probe.py)：只发 24 个中性包（左右均 `00 01 40 40`），手动点击 + 6 秒倒计时，传输上限 50 ms，发送前逐包断言中性，不写配置、不发初始化/Feature 命令、不接触 Pico。

开关族 28 项测试全过；L0 扩到 376 项、12.175 s、hardware_actions=0（[证据](campaigns/realtime-2026-11-15/l0-regression-20261116-1400.json)）。离线记录见 [switch-usb-timing-offline-20261116.json](campaigns/realtime-2026-11-15/switch-usb-timing-offline-20261116.json)。

边界：这只证明策略与报文边界正确，真实传输时间仍未测量；WriteFile 完成不等于手柄 ACK；中性包试次不能证明震动能力。下一步是一次只读的中性包时序采集，再据实测给活动帧定传输上限，不放宽派发 4 ms 与断流 80 ms。
