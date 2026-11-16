# 经典 HID 主机探针：2026-11-16 结果

## 目标

让 Pico2W（CYW43）作为蓝牙 HID 主机，直接连飞智八爪鱼 6 Pro（"xinput蓝牙"模式），
发 Xbox 0x03 输出报告让手柄震动。全程 RAM-only：不写 Flash、不碰飞智持久配置。

## 代码与产物

| 项 | 位置 / 值 |
|---|---|
| 经典 HID 探针 | `standalone/bt_hid_classic/`（target `flydigi_bt_hid_classic`） |
| 探针脚本 | `work/bt_hid_classic_probe.ps1`，日志 `work/bt-captures/bt-classic-*.log` |
| 镜像 | text ~370 KB，RAM 运行，`flash_range_erase/program` 调用点 0 |
| BLE 扫描探针（改主动扫描） | `standalone/bt_discovery/`，`work/bt_discovery_probe3.ps1` |

## 今天修掉的两个真 bug

1. `cyw43_arch_poll()` 在无线电初始化前被无条件调用 → 加载后固件立即崩溃、USB 消失。
   修法：`if (phase) cyw43_arch_poll();`。
2. `btstack_config.h` 缺 `MAX_NR_HID_HOST_CONNECTIONS`，`hid_host_connect()` 返回
   `0x56` = `BTSTACK_MEMORY_ALLOC_FAILED`。修法：`#define MAX_NR_HID_HOST_CONNECTIONS 1`。

## 实测结果

经典链路：

- inquiry 稳定命中 `74fb56e7b698`（逆序 `98:B6:E7:56:FB:74`），CoD `0x000508`；
- `HCI_CONNECTED status=0x00 link=1`（ACL 建立成功）；
- 之后 **20 秒内没有任何 L2CAP/SDP 报文**，也没有 `IO_CAP_REQUEST` / `AUTH` 事件；
- 主动补发 `HCI_Authentication_Requested` 后仍然没有 SSP 交互；
- 约 20 秒后被对端以监督超时 `0x08` 断开。

BLE：

- 电脑蓝牙关闭、手柄"配对中"时，主动扫描 40 秒共 1020 条**可连接**广播，
  没有一条带 Microsoft `0x0006`，也没有 Xbox/Flydigi 名字；
- 同一时刻经典 inquiry 能命中它；
- 结论：该模式下手柄**不发 BLE 广播**；Windows"添加设备"能看到它，是经典发现。

## 当前判断

- 手柄在这个模式下是可被经典 inquiry 发现的设备，但 ACL 建立后不响应任何上层交互；
- 有两种可能：(a) 它要求由它已绑定的主机发起（我们不是）；(b) 经典侧只用于发现/配对，
  实际 HID 走别的通道（但本次未观测到 BLE 广播）。
- 尚未证明"经典 HID 主机可以驱动它"，也**没有**任何一次成功震动。

## 安全状态

- 全程 `host_flash_write=false`、`persistent_flydigi_commands=0`；
- Pico 每次实验结束都回到 BOOTSEL；
- 未修改飞智原厂配置。

## 下一步候选

1. 用 Windows 抓一次"从添加设备到手柄可用"的完整空口过程（需要空口抓包工具），
   看它到底走经典 HID 还是 BLE HOGP、配对参数是什么；
2. 若确认经典 HID：对齐 Windows 的 SSP 参数（IO capability、bonding、MITM）再试；
3. 若确认 BLE：需要在"手柄刚进配对的头几秒"用可连接广播捕获并立刻连接；
4. 兜底：继续用已验证的 USB 有线桥（Pico 插主机、USB 直连），把"离线直连手柄"作为后续目标。
