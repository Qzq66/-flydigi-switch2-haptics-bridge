# 蓝牙 HID 主机（Pico 直连飞智手柄）— 2026-11-15 晚

目标：让 Pico2W 作为主机，**直接**通过蓝牙连上飞智八爪鱼 6 Pro，并向它发送震动输出报告，
不经 Windows、不经 Wi-Fi。

安全边界（全程遵守）：

- 只用 RAM-only ELF（`PICO_NO_FLASH`），不写 Flash、不生成 UF2。
- 不配对持久化：蓝牙 TLV 存储被链接器 wrap 进 8 KiB RAM bank。
- 不写飞智原厂持久配置；不 reset / 不升级 / 不切槽。
- 每次实验前 `picotool save -a` 前后整片哈希一致才算“没过写 Flash”。

## 结论（今晚定死的）

**飞智的「xinput蓝牙」模式不发 BLE 广播，它走经典蓝牙（BR/EDR）HID。**

支撑证据：

1. BLE 全量扫描 40 秒，3375 行广播，只看到邻居设备：
   `Beoplay`（两个地址）、`hellobike`、`Mijia`、`YINPAGE`、`WH-1000XM5`、一个乱码名设备。
   没有任何 `Xbox` / `Flydigi` / `Apex` / `Pro` 名字，也没有 Microsoft 厂商号 `0x0006`。
2. 手柄已知的 BLE 地址 `0C:35:26:56:A0:22` 在整轮扫描中**一次都没有出现**。
3. 手柄关机后扫描仍有 12 个地址的 `evt=3` 广播 → 之前看到的那些不可连接广播是周边设备，不是它。
4. 经典 inquiry（较早一轮）在配对态下命中 `98:B6:E7:56:FB:74`，CoD `0x0508`（外设/手柄），
   与 Windows 设备树里的 `BTHENUM\DEV_98B6E756FB74` 完全一致。
5. Windows 侧同时有 `BTHENUM\DEV_98B6E756FB74`（经典）与 `BTHLE\DEV_0C352656A022`（BLE），
   但震动实测（XInput 三段 BOTH / LEFT / RIGHT，用户确认三段都震）走的是已配对链路，
   不能据此推断空中接口；空口证据以扫描为准。

因此 HOGP（BLE HID over GATT）方向作废，改为经典 HID 主机。

## 已完成的代码

### 1. `standalone/bt_discovery/`（只读发现探针，已硬件验证）

- BTstack 经典 inquiry + BLE 被动扫描，只输出到 USB CDC，不配对、不连接、不写 Flash。
- RAM 运行，跑完回 BOOTSEL；`MAX_OBSERVATIONS` 已从 32 提到 96。
- ELF：`standalone/bt_discovery/build-ram/flydigi_bt_discovery.elf`，
  text 331936 / bss 32408 / 364344 B，
  sha256 `d0419ee6efd90748e52ded1d010c8e4da0610869e32ff06b15fc1f30aacf7069`，
  与 `docs/campaigns/realtime-2026-11-15/bt-discovery-offline.json` 一致。

### 2. `standalone/bt_hid/`（HOGP 主机探针，方向已作废但代码保留）

- `main.c` 的流程：READY → `SCAN` → radio → LE 扫描 → 匹配 → 连接 → Just Works 配对 →
  HID 服务发现 → 发 4 组 report 0x03 → 发零 → 断开 → BOOTSEL。
- 现为全量观测版：任何广播/扫描响应都打印 `evt / addr / rssi / name`，
  连接条件为“可连接 + 名字像手柄（xbox/flydigi/apex/pro）或 Xbox 厂商号”，
  避免再被耳机之类的设备带跑。
- ELF：`standalone/bt_hid/build-ram/flydigi_bt_hid.elf`，text 388916 / bss 24924 / 413840 B。
- 反汇编核对：`flash_range_erase` / `flash_range_program` 调用点为 0。

### 3. 扫描脚本

- `work/bt_hid_probe.ps1`：`picotool load -x` 装 RAM ELF → 等 CDC → 开串口（DTR/RTS，115200）
  → 发 `SCAN` → 抓 95 秒 → `BTH2 DONE` 结束，原始日志存 `work/bt-captures/bt-hid-<stamp>.log`。
- 记录：`work/bt-hid-run5.log` … `work/bt-hid-run10.log`。

## 明天的下一步：经典 HID 主机

新建 `standalone/bt_hid_classic/`（或改造现有目录，二选一，明天定）：

1. `gap_inquiry` 经典 inquiry，过滤 CoD 主要设备类 `0x05`（外设）且次要类为手柄/摇杆；
2. 命中后 `hid_host_connect(addr, HID_PROTOCOL_MODE_REPORT, &hid_cid)`；
3. 等 `HID_HOST_CONNECTION_ESTABLISHED` / `HID_SUBEVENT_CONNECTION_OPENED`；
   若被要求认证，用 Just Works（`hci_set_ssp_io_capability` / 无输入输出）；
4. `hid_host_send_set_report(hid_cid, HID_REPORT_TYPE_OUTPUT, 0x03, payload, len)`
   发 8 字节 Xbox 风格载荷（enable flags、扳机、左右马达、时长等），依次试强/左/右；
5. 发全零载荷，`hid_host_disconnect`，回 BOOTSEL；
6. 全程打印 `BTH3 …` 前缀日志，脚本 `work/bt_hid_classic_probe.ps1` 照搬现有探针结构。

API 已确认存在：`hid_host_register_packet_handler`、`hid_host_connect`、
`hid_host_send_set_report`（`standalone/deps/btstack-eb0bb8b/src/classic/hid_host.h`）。

风险与判据：

- 经典 HID 的输出报告格式/报告 ID 可能与 BLE 不同，需要先试 `0x03`，不行再枚举 0x01/0x02。
- 若手柄要求绑定（bonding），RAM 里存不了密钥，断连后需重新配对——这正好符合“不写 Flash”的边界。
- 判据仍然是“用户感到震动”，没有其他客观量。

## 复现命令要点

```powershell
# 构建（必须用 VS2022 自带 cmake + SDK 自带 ninja）
& 'C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe' `
  --build standalone/bt_hid/build-ram --target flydigi_bt_hid --parallel 2

# 装 RAM ELF 并抓串口
powershell -NoProfile -ExecutionPolicy Bypass -File work\bt_hid_probe.ps1
```

环境注意：本机是 Windows PowerShell 5.1（无 pwsh）；`.ps1` 受执行策略限制；
脚本写 UTF-8 无 BOM 时中文路径会乱码，脚本里避免中文、用通配符定位 picotool。

## 未验证 / 边界

- 未证明 Pico 经典 HID 能成功配对并驱动震动——这是明天的实验。
- 未证明「xinput蓝牙」模式下输出报告就是 0x03。
- 今晚没有写任何 Flash、没有改飞智配置；`picotool save -a` 前后哈希一致（run 5 已验证）。
- 电脑端三段震动是 Windows 链路的结果，只说明“手柄硬件支持震动”，不说明 Pico 链路可行。
