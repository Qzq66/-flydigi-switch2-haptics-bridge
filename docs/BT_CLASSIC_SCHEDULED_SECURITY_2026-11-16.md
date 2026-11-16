# Classic认证调度候选v4（离线完成，未加载）

上轮认证发送函数同步返回0x0C。固定版本BTstack `hci.c:8699` 显示，命令发送条件不满足时会在本地返回该错误；不能视为手柄拒绝认证。

## 修正与依据

探针取消连接回调里的原始`hci_send_cmd(Authentication Requested)`，改为一次`gap_request_security_level(handle, LEVEL_2)`。固定版本实现`hci.c:9174`设置连接认证状态，交由状态机等待远端能力查询及命令发送条件；`hci.c:8122`执行排队认证。

LEVEL_2要求认证/加密，不要求MITM；原有SSP no-bonding和RAM密钥存储保持不变，不调用持久绑定或清除配对。增加`SECURITY_RESULT`日志，避免将“提交请求”误判为认证完成。无自动试次重试、无输出报告、不变更震动保护参数。

## 检查

v4 RAM镜像编译通过，现场入口为`work/bt_classic_scheduled_security.ps1`，保留旧v3入口。脚本语法检查通过，反汇编中Flash擦写与HID Output发送的直接调用均为0。哈希和检查结果见 [离线证据](campaigns/realtime-2026-11-15/bt-classic-scheduled-security-20261116.json)。本轮未接触设备。

下一次现场仍只做一次无震动连接：确认电脑蓝牙关闭、手柄正常进入xinput蓝牙配对态；实际BOOTSEL、完整Flash前后校验及目标锁定照常执行。判据分别记录认证完成、安全级别结果、HID打开状态及描述符，任一步失败保留日志并停止，不自动变更策略。Pico侧RAM存储不保证手柄侧绑定记录绝对不变，不清旧配对、不恢复出厂。

## 单次现场结果（v4，已结束）

用户确认电脑蓝牙关闭及设备就绪后，执行一次无震动RAM试次。出现目标ACL、BTstack安全请求、密钥请求、IO_CAP_REQUEST及IO_CAP_RESPONSE；随后SECURITY_RESULT为level=0/status=0x05，AUTH为0x05（Authentication Failure），HID打开0x81（SDP Query Incomplete）。没有描述符或马达输出；完整4 MiB Flash哈希一致且物理verify成功，Pico已回BOOTSEL。

这是相对v3的明确推进：认证流程已经进入IO能力交换，不再卡在应用抢发命令返回0x0C。仍不能据此证明手柄拒绝所有Pico主机或不支持Classic HID。

固定版本`hci.c:8007`附近根据本地bondable标志构造SSP回复；目前探针明确发送no-bonding。0x05的根因仍未证实，可能涉及双方配对策略等；现有日志未记录对端完整IO能力/认证需求，不能认定必须开启bonding。未改变策略或再次现场重试。下一步先补全这些字段及本地SSP决策证据；任何bonding对照需明确说明可能改变手柄侧蓝牙绑定，不能以Pico RAM-only为零影响保证。

见 [现场证据](campaigns/realtime-2026-11-15/bt-classic-v4-field-20261116-112752.json)。
