# 双方配对要求核对（只读，2026-11-16）

结论：Pico策略已确认，飞智对端具体字段未被旧日志保存，不能完成双方匹配判断，也不能认定必须开启bonding。未连接设备、未改变策略。

## 已确认的Pico策略

| 项目 | 当前值 | 源码依据 |
|---|---|---|
| IO能力 | NoInputNoOutput | `standalone/bt_hid_classic/main.c:259` |
| 安全级别 | LEVEL_2：加密，不要求MITM | `main.c:165`；`src/gap.h:83`附近 |
| SSP绑定 | No bonding；bondable=0 | `main.c:260`、`:261` |
| OOB | 未提供OOB数据，未启用Classic OOB配置 | 当前探针与btstack_config.h |
| 用户确认 | SDK默认ssp_auto_accept=0；应用仅记录USER_CONFIRM，没有调用confirmation_response | `src/hci.c:5603`；`main.c:195` |
| 本机密钥存储 | RAM bank，不写Pico Flash | ram_bank.c与ELF调用审计 |

以上BTstack路径相对于`standalone/deps/btstack-eb0bb8b/`，对应固定提交，不引用其他版本行为。NoInputNoOutput并不代表应用已经实现完整Just Works确认流程。Pico不持久化密钥也不代表手柄端不会记录绑定。

## 对端已经知道和不知道的内容

v4现场已记录LINK_KEY_REQUEST、IO_CAP_REQUEST、IO_CAP_RESPONSE，随后AUTH=0x05、安全级别0、HID=0x81。说明认证交换已经推进，不能视为“完全不响应”。

但是`main.c:192`仅打印IO_CAP_RESPONSE标签，没有保存实际io_capability、oob_data_present、authentication_requirements。固定SDK读取这些字段的位置分别为`src/btstack_event.h:1279`、`:1288`、`:1297`。无法从当前文本日志恢复这三个字节。

用户确认Windows以前能够识别连接；这证明存在Windows可用的配对方式，不能推出与当前Pico no-bonding策略相同。电脑已取消配对并关闭蓝牙，不证明手柄端旧密钥清除。

## 可证实的兼容条件与未证实的根因

1. SDK `src/hci.c:4222`：收到对端Dedicated Bonding要求且本机非bondable时，会拒绝。当前未保存对端AuthReq，故该冲突仅为候选，不能定因。
2. SDK `src/hci.c:8013`附近：本地bondable标志参与构造实际SSP认证需求；不能只看ssp_authentication_requirement字符串认定线上的参数。
3. SDK `src/hci.c:4893`：若出现确认请求，auto_accept关闭且应用不答复，流程可能无法完成。v4日志没有USER_CONFIRM，故这属于未来流程缺口，不是本次0x05的已证实原因。
4. v4的0x05表示认证失败；无法仅凭错误码区分绑定策略、旧密钥或其他配对问题。SDP 0x81是本轮后续失败，不能证明没有HID服务。

## 最小下一步

下一候选只补充日志：对端IO/OOB/AuthReq、连接地址与锁定目标匹配结果、本地IO/安全级别/bondable/auto_accept、认证与加密状态。保留当前策略，不启用自动接受、不清密钥、不切绑定策略、不发送Output或Feature报告。

如需现场，只进行一次相同策略的无震动采集以补齐字段，不重复幅度/游戏测试。拿到具体字段后才决定是否需要单独说明并授权绑定策略对照；不同时试多套参数。历史证据见 [v4现场](campaigns/realtime-2026-11-15/bt-classic-v4-field-20261116-112752.json)。

## v5字段候选已离线完成

已加入remote_io、remote_oob、remote_authreq以及本地IO/bondable/auto_accept等策略标签，确认请求明确记录action=none。仅增加日志和版本标识，不接受确认、不切绑定策略。v5 RAM镜像编译、入口脚本语法及无Flash/Output直接调用检查通过，尚未加载。入口`work/bt_classic_pairing_fields.ps1`要求v5版本；哈希见 [v5离线证据](campaigns/realtime-2026-11-15/bt-classic-pairing-fields-20261116.json)。

## 公开协议资料复查（2026-11-16）

- [飞智官方Connection Guide](https://flydigiglobal.helplook.com/docs/Connection-Guide)：明确提供PC XInput Bluetooth连接步骤，属于连接说明，未提供当前配对/HID/触觉报告格式。
- [ApexSenseBridge](https://github.com/ReynArts/ApexSenseBridge#supported-controllers)：APEX 6 Pro支持表列2.4GHz Dongle/Wired USB，不能视为蓝牙精细波形已有验证。
- [ApexSenseBridge-Linux](https://github.com/RafaelDiasCampos/ApexSenseBridge-Linux)：公开实现同类触觉/输入，可作USB/接收器参考，未据此确认本机蓝牙输出能力。
- [openflydigi](https://github.com/mkaliaha/openflydigi)：APEX 6/Pro实验性支持说明明确提到接收器和直连USB，不能扩展推断到蓝牙。
- [flydigi-space-station-mac协议文档](https://github.com/uiltonlopes/flydigi-space-station-mac/blob/main/docs/protocol.md)：涉及其他代际、BLE配置通道的边界，不是APEX 6 Pro蓝牙精细触觉证据。
- 搜索命中的[flydigictl PROTOCOL](https://github.com/ElXreno/flydigictl/blob/main/docs/PROTOCOL.md)实际为BS系列散热器，虽同品牌且写有蓝牙HID，不可用于手柄。

结论是“本次核对范围内未找到已验证APEX 6 Pro蓝牙精细波形实现”，不是证明网络上绝无协议。标准蓝牙配对、SDP、HID Host已有BTstack实现，无需自造；当前需要匹配实际手柄配对要求，获取描述符后再判断输入和输出。没有下载或执行上述项目二进制、发送其配置命令或复制整合源码。

## v5现场补采结果：双方字段已取得

一次无震动试次完成，用户确认电脑蓝牙关闭及手柄配对态。双方具体字段：

| 字段 | Pico当前策略 | 手柄回复 |
|---|---|---|
| IO capability | 3：NoInputNoOutput | 3：NoInputNoOutput |
| OOB | 0：无 | 0：无 |
| Authentication requirements | 0：No Bonding，无MITM | 4：General Bonding，无MITM |

值的解释来自固定SDK `src/bluetooth.h:484`至`:511`。本轮随后仍为AUTH=0x05、安全级别0、HID=0x81，无描述符、无USER_CONFIRM事件。

双方绑定意向不同已证实，但“手柄必须绑定、差异就是失败根因”尚未证实。特别是此前检查到SDK主动拒绝的规则针对Dedicated Bonding(2/3)，不能套用到本次General Bonding(4)。当前不需要MITM数字比对；也不能把应用没有确认答复直接归因为本次失败。

Pico完成全量Flash前后回读及physical verify，哈希一致、输出报告0、RAM错误0，已回BOOTSEL。[现场证据](campaigns/realtime-2026-11-15/bt-classic-v5-field-20261116-114205.json)。

下一候选是单条件允许General Bonding的无震动对照，其他策略不变，Pico密钥仍只在RAM，不能自动开启。其风险是手柄自身可能持久保存新的蓝牙主机绑定，Pico断电后本机密钥消失可能造成后续重连需重新配对。此风险不同于修改飞智马达/配置槽，但属于用户需要明确同意的配对策略变化；不删除旧配对或自动恢复出厂。当前尚未制作或执行该变体。

## v6 General Bonding候选（后续进展）

用户在上述风险说明后回复“继续”，据此准备该范围内单次无震动对照。候选仅将本地SSP认证需求设为General Bonding且bondable=1，保留LEVEL_2、NoInputNoOutput、auto_accept=0、RAM存储和无Output报告；不清除配对，不执行设备重置。

已保存v5源码到private，v6镜像编译、入口语法及无Flash/Output直接调用检查通过；尚未加载。入口`work/bt_classic_general_bonding.ps1`绑定v6串口版本。[离线证据](campaigns/realtime-2026-11-15/bt-classic-general-bonding-20261116.json)。开始前仍需确认实际BOOTSEL与配对状态，并执行全量Flash前后核对。若出现USER_CONFIRM，仅记录而不自动答复；本轮不会同时改变确认策略。

## v6单次现场对照已完成

最终镜像绑定 [final离线证据](campaigns/realtime-2026-11-15/bt-classic-general-bonding-final-20261116.json)。用户确认设备就绪后执行一次，结果：本地IO=3/OOB=0/AuthReq=4/bondable=1，远端IO=3/OOB=0/AuthReq=4；随后安全级别0/status=0x05、AUTH=0x05、HID=0x81，无USER_CONFIRM、无描述符、无Output报告。Flash完整前后哈希相同，physical verify通过，Pico回BOOTSEL。见 [v6现场证据](campaigns/realtime-2026-11-15/bt-classic-v6-field-20261116-114819.json)。

可判定：“只将No Bonding改为General Bonding即可成功”未获支持；双方绑定意向一致不足以让认证通过。不能扩大为“绑定策略完全无关”，也不能在没有确认事件时归因于未自动接受。不能声称手柄已保存新密钥或绝无绑定状态变化；当前仅知道本轮认证失败。

不自动继续现场试次，不开启auto_accept或清密钥。下一步优先离线审查安全能力（SSP/Secure Connections等）与失败前后的HCI事件记录方案；如需补采，只捕获与目标相关、足以区分本机拒绝和远端失败的事件。原始日志必须private，密钥/设备身份不得公开；不抓取或打印Link Key Notification的密钥内容。没有进一步证据前不随机切参数或发送猜测性震动报告。

## v7安全事件元数据候选（只完成离线工作）

核对固定SDK `hci.c:5600`、`:5606`：SSP和Secure Connections默认启用。当前代码未关闭它们，但控制器支持/实际启用及远端协商结果仍须现场证据，不能把默认值当成失败根因。

新增`standalone/bt_hid_classic/security_trace.c`，通过SDK现有hci_dump回调只打印白名单字段：

- 本机实际IO回复中的IO/OOB/AuthReq，IO负回复的reason；认证、密钥负回复、确认正/负回复的opcode。
- SSP/SC host支持设置；本机支持特性、远端基础/扩展特性页。
- Simple Pairing Complete及Encryption Change的状态；相对时间戳。

不打印Link Key Reply/Notification、数字确认值、地址或通用数据包；不转发SDK任意日志字符串。新增trace最多96条，按事件生成少量元数据；没有改变v6安全策略、启用自动接受或引入新硬件命令。旧主日志仍含地址，整个capture必须留private。HCI日志属于主机/控制器边界，不能声称是空口抓包或证明错误一定来自手柄；TX记录也不等于包已到达手柄。

v7编译与入口语法检查通过，Flash擦写与HID Output直接调用审计为0。入口`work/bt_classic_security_trace.ps1`，证据和哈希见 [v7离线记录](campaigns/realtime-2026-11-15/bt-classic-security-trace-20261116.json)。未现场加载，尚未验证运行时trace。

下一次如用户就绪，只做一次同策略无震动对照，预期区分：是否本机主动发出负回复、实际SSP参数与设置是否一致、失败发生在能力交换还是Simple Pairing阶段。若仍不能定位，应据实说明证据不足，不自动继续循环试参数。

## v7现场结果：范围缩小，根因仍未证实

单次采集完成，前后完整Flash哈希与physical verify通过，Pico回BOOTSEL，Output报告0。见 [v7现场](campaigns/realtime-2026-11-15/bt-classic-v7-field-20261116-115807.json)。

- 本地基础能力`bffecffedbff7b87`；SSP Write Simple Pairing Mode=1，Write Secure Connections Host Support=1，stack报告sc_active=1。
- 远端特性页0=`bffe8dfec82d7983`，页1=`0100000000000000`，页2全0；查询状态均成功。
- 按固定SDK `hci.c:2810`、`:2827`、`:2838`解码，远端SSP Controller/Host位为1，而SC Host/Controller位为0，`hci_remote_sc_enabled`应为false。这表示本次报告的是旧式SSP能力，不是SC；不能据此推断其Bluetooth版本或断言本地SC启用就是失败根因。LEVEL_2不要求SC，SDK具备非SC路径。
- 主机向控制器提交了Authentication Requested、Link Key Negative Reply和实际IO回复io=3/oob=0/authreq=4，双方IO/OOB/AuthReq一致。Link Key Negative Reply仅表示Pico没有该对端密钥，不等于拒绝新配对。
- 未记录TX_IO_NEGATIVE或确认负回复；无USER_CONFIRM事件。约20.23秒后收到Simple Pairing Complete=0x05，随后AUTH=0x05、HID=0x81。没有加密成功或描述符。

这排除了“应用未提交IO回复”及“记录到本机主动拒绝”等直接解释，但不足以证明故障责任在远端；白名单HCI记录不是完整空口或固件内部状态。0x05本身不提供更具体根因，约20秒间隔也不能直接改称已证实超时根因。保持General Bonding和确认策略不变，没有继续现场重试。

下一步优先使用成功的Windows连接作为协议对照或核对当前BTstack/CYW43与旧式SSP的兼容路径；若涉及重新开启电脑蓝牙/重新配对或安装抓包组件，需先明确具体动作和证据目的，不自动执行。不能把“改禁用SC再试”当已确认修复，也不再重复原参数无信息增益的试次。
