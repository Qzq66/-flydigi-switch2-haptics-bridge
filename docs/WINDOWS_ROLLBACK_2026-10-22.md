# 回到旧 Wi-Fi 提示方案，2026-10-22

用户明确说明没有 USB 转 TTL，要求回到之前方案。停止推进串口方案，不要求购买新硬件。本次回滚是独立的后续动作；此前无输出和 RAM 诊断报告保留，不修改其失败结论。

## 已完成

1. 用户拔下 Pico 后，原电脑热点配置及原开关状态恢复并比较成功。
2. 从保留的原 Windows 工作区冻结旧源码、成功证据、专用网络参数、固件和完整原 Flash 备份，单独放入当前 checkout 忽略目录 work/private。没有重置 Git，也没有丢弃 Mac 重构及本轮诊断。
3. 选择此前主机登记页实际体感通过的组合：Pico v040 Flash + 电脑端 120ms、±12 的提示模式。电脑端尚未启动；game-pilot 为 false。
4. 用户将 Pico 置于 BOOTSEL 后，先使用 picotool 对当前完整 4MiB Flash 与原始备份逐字节 verify，再安装旧固件并读回验证成功。只更新程序所在区域，擦写范围 [0,0x57000)，未写飞智原厂配置。本次安装没有启动固件或输出。
5. 当前 Pico 停在 BOOTSEL，专用热点未启用。后续启动会运行旧测试固件，而不是 MicroPython；恢复 MicroPython 要用已核验的完整原 Flash 备份。

证据见 WINDOWS_ROLLBACK_PREPARATION_20261022-202421.json、WINDOWS_ROLLBACK_INSTALL_console.txt 和本目录 WINDOWS_ROLLBACK_INSTALLED_*.json。

## 已核验材料

- 旧固件 354708 字节，SHA256 `0cef76fe7ade60477d5f375a83830ac5877c39b9e28ed677a9cd595049904f34`。
- 完整原 Flash 4194304 字节，SHA256 `09762691d3fddf3ba592db0bb6f520cb2384423f37194e7974089c9b0f700593`。
- 私密选择文件：`handoff/2026-10-22/work/private/rollback-selection.json`，记录冻结目录、旧入口、镜像、完整恢复备份及参数。不要上传此目录。
- 下次启动旧热点应使用冻结目录 work/pico-hotspot.ps1 -BridgeNetwork，由该目录新建的 DPAPI 记录保存启动前的原热点；结束用同目录 restore-pico-hotspot.ps1。不能用本轮 v042 的新热点凭据配旧镜像。
- 下次旧入口参数为 `--prompt-ms 120 --prompt-offset 12`，不自动启用 game-pilot。执行前仍需身份及四区备份，父进程独立停止，结束核对配置；需要提示用户后再换接离线主机。

## 保留的限制

旧方案仅在登记页提示体感通过，最后一次303个马达字段只收302个，缺最后中性尾帧。没有完整游戏闭环、结束握手或保真验收；回滚不保证解决当前环境测得的96~201ms网络间隔，不得放宽80ms保护线。旧父进程/收尾逻辑不能沿用其宽松成功判定作为新版验收。

用户已用原装 Joy-Con 确认《空之轨迹2nd》“B 闪避后接 A 攻击”有较弱震动。该动作可作为未来对照，当前仍不算桥接游戏证据。

## 回滚后登记页复测

见 WINDOWS_LEGACY_PROMPT_RECHECK_20261022-202834.json、WINDOWS_LEGACY_CAPTURE_20261022-2032.json 和 WINDOWS_LEGACY_RECHECK_ASSESSMENT_20261022_CORRECTED.json。主机日志CRC正确，无丢弃，保存303个马达字段，含左右各一个活动参数组；电脑只收到前20个字段，逐字节与主机日志前缀一致。心跳超时保护触发前输出左侧36个样本，右侧0，未完成两侧120ms提示，程序结果INCOMPLETE。两级停止确认及四区配置核对均通过，热点已恢复，Pico停在BOOTSEL。

用户最初选择了含“左右明显震动”的组合选项，随后明确更正：只握左握把，未握右握把。因此本次只确认左侧体感，右侧未验证；不能把原组合选项解释为右侧体感通过。最初派生判断保留以供追溯，以CORRECTED报告为准。此次更正不改变此前16:27独立试验的原始证据，也不改变本次程序超时失败结果。

## 当前连接选择

平板热点对照未能完成联网，用户要求停止该尝试并切回电脑热点。详见 WINDOWS_TABLET_NETWORK_2026-10-22.md。与旧固件匹配的专用电脑2.4GHz热点已重新启动，启动前客户端0；Pico仍在BOOTSEL，旧Flash经RAM试验前后完整比较一致，没有监听或输出进程。当前不再推进平板或串口；心跳超时仍是待解决问题。
