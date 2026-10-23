# Windows 硬件恢复测试，2026-10-22

基线 main `d3442d90d75b3ada8ccdf535257c5859dfb074c9`。从 WINDOWS_RESUME_2026-10-22.md 接续；用户明确恢复硬件测试。本轮只在电脑上运行，没有连接 Switch 2，没有向 Pico Flash 写入，没有原厂持久配置写命令。

## 已实测

- 十二组离线检查 301 项通过，见 WINDOWS_OFFLINE_RECHECK_2026-10-22_resume.json。
- Windows HID owner、四区备份及读回、计时器 acquire/release 和唯一 XInput 槽位实测通过，见 WINDOWS_HARDWARE_PREFLIGHT_20261022-195945.json。人为 A 键按下/释放挑战通过，见 ../handoff/2026-10-22/outputs/xinput-source-confirmation-20261022-200101.json。
- SDK 2.3.1 / GCC 14.2.1 编译 v042 RAM，UF2 609280 字节；写地址全部在 0x20000000..0x2004a600。RAM load/verify 成功；本地实际网络参数编译，镜像不上传。
- Pico USB 注入 → 真实 Wi-Fi → 当前 Client：307 条马达字段连续且逐字节一致，重复 0、溢出 0、日志 CRC 有效，明确结束及最终确认通过。按键转发、失去输入后回中、Home 注入拒绝检查通过。见 WINDOWS_RAM_CAPTURE_RECHECK_20261022-200607.json 和 ../handoff/2026-10-22/outputs/pico-bridge-v042-raw-test-20261022-200702.json。
- 保留 2265 个完整原始收发 UDP 报文，以及真实 64KiB RAM 日志。原始 UDP 含会话标识，只留在忽略目录 work/private；公开报告保留全部解码事件，不含会话标识。RAM 预览在 ENDLAB 前读取，不能算持久 END2 验证。
- 重构后的 Windows owner/TimerResolution 和 communicate_bounded 独立诊断：正常结束、主动异常、子进程超时强制结束三种实测通过。诊断波形上限 ±12、正常提示 120ms，异常/超时更短。每轮父进程独立停止并核对身份、状态、global/mapping/lighting/motors 四区全部一致。见 WINDOWS_OWNER_PROCESS_RECHECK_20261022-200945.json。强杀不会执行子进程 finally，停止依赖独立父进程；正常/异常路径计时器释放已验证。

## 收尾与边界

Pico 已恢复原 MicroPython，电脑识别 COM11。临时热点已恢复并核对原配置和开关状态；首次恢复因客户端缓存尚未消失被拒绝，随后无客户端时恢复成功，没有绕过检查。飞智输出已停止，三轮均收到运行模式关闭确认，配置一致。用户随后明确确认三次都及时停止、没有持续残留。这是人工触感确认，没有测量马达的物理停止延迟。

本轮 v042 使用原始实验线程轮询当前 Client；完整 live collect_frames 线程与父子进程的合并路径仍需下一轮验证。父子进程诊断是受控波形，没有宣称来自主机或游戏。未测试新版 Flash、持久 END2、掉电日志、Switch 游戏按键/震动闭环，也未证明 HD Rumble2 保真。

后续整合实测见 WINDOWS_INTEGRATED_RAM_RECHECK_20261022-201532.json：确实使用当前 collect_frames、Renderer、真实网络及独立父进程收尾，但只运行 23 个中性波形块即触发 `wire heartbeat timeout`，最大偏移 0，没有播放有效震动。本轮状态 INCOMPLETE，不能算桥接通过。子进程和父进程停止确认均通过，四区与状态均一致。Pico 回到原 MicroPython，临时热点恢复。追查此前完整 RAM 报文，911 个有效帧之间有 227 个间隔超过 80ms，最大 121.545ms；完整性通过不能代替实时性通过。保留原80ms保护线，进一步进行无输出网络时序诊断。

用户已用原装 Joy-Con 确认《空之轨迹2nd》“B 闪避后接 A 攻击”会产生较弱震动，可作为后续对照动作；尚未用本桥接验证该游戏动作。

无马达网络诊断见 WINDOWS_NETWORK_TIMING_RECHECK_20261022-201812.json：BHP2 和 BHI2 中性输入各测约15秒，分别702/625个有效回复、147/148次轮询超时，最大有效帧间隔95.667/200.892ms。完整收包线程收到先 draining(9) 再 complete(25)，结束确认成功。原始1610个接收报文中281个对应已过期的请求，但即使统计所有原始接收包，仍有181个间隔超过80ms、最大199.874ms；不能只靠接纳过期回复解决实时问题。诊断没有打开飞智接口，没有马达输出，没有改保护线。网络层延迟已证实，根因尚未定位（不能据此归因到热点、射频、Pico驱动中的某一项）。等待用户将 Pico 断电以退出无线关联，随后恢复临时热点；已询问现有 USB 转 TTL 型号/电平，仅准备有线备选，不允许未核实便接线。

## 接续顺序

1. 本轮停止触感已确认无残留；后续如出现残留，停止推进，先诊断。
2. 电脑端以 v042 RAM、完整 collect_frames 和父子进程整合已捕获的主机报文；通过后再换接 Switch，避免将当前独立检查算成完整桥接验收。
3. Flash 前重新核对本地原 Flash 全备份及恢复工具，再验证持久 END2。
4. 原装 Joy-Con 的“B 闪避后接 A 攻击”震动已确认；实时链路稳定后再做相同动作的桥接验证。保持离线及有线通信选项，受限提示仍是固定 120ms 通知映射。

本地备份、会话、实际网络参数及 UF2 都位于忽略目录。新增证据和工具尚未提交或上传 GitHub。

后续用户说明没有串口模块，要求回滚旧 Wi-Fi 方案。已恢复热点、冻结旧方案并核验备份后，将旧 v040 Flash 安装到 Pico，读回验证成功，保持 BOOTSEL，尚未启动输出。当前设备状态以 [回滚记录](WINDOWS_ROLLBACK_2026-10-22.md) 为准；前文无 Flash 写入和 MicroPython 状态是回滚之前的 RAM 测试收尾状态。
