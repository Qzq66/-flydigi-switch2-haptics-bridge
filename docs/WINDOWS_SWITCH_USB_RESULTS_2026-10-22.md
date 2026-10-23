# iPhone USB供网后的Switch 2真实主机复测

2026-10-22。网络拓扑继续为iPhone USB供网 → Windows原专用2.4GHz热点 → Pico。电脑原5GHz WLAN关联断开。用户让Switch 2离线、进入更改握法/顺序并开启一代Pro有线通信；Pico经CM473换接主机，随后按BOOTSEL接回电脑。

## 结果：真实主机受限提示通过

程序报告 [WINDOWS_LEGACY_PROMPT_RECHECK_20261022-212056.json](WINDOWS_LEGACY_PROMPT_RECHECK_20261022-212056.json)，原始主机捕获解码 [WINDOWS_SWITCH_USB_CAPTURE_20261022-212056.json](WINDOWS_SWITCH_USB_CAPTURE_20261022-212056.json)，独立核对 [WINDOWS_SWITCH_USB_VERIFICATION_20261022-212056.json](WINDOWS_SWITCH_USB_VERIFICATION_20261022-212056.json)。

- 主机本地日志第2代，CRC有效，304条USB记录中302个马达字段，无日志溢出。电脑收到302/302个字段，内容逐字节匹配，序号连续；左右活动参数组都收到。本次没有缺失尾字段，不能倒推此前302/303反例为完整通过。
- 输出2125个8ms块，左右各1次120ms通知，实际最大偏移12，左右各5个源活动样本映射为各120个输出样本。两侧提示完整。
- 用户明确双手分别握住握把，确认图标出现、左右都有清楚短震动、及时停止。
- 子进程正常退出，独立父进程没有强杀。两级运行模式关闭确认均通过，身份、当前状态和global/mapping/lighting/motors四区与备份一致，没有飞智原厂持久配置写命令。

## 收尾限制

本次仍使用保留的v040固件和冻结Windows提示引擎，外层使用更严格的独立父进程监护。旧固件定时捕获结束后断开，程序最终原因记录为wire heartbeat timeout；没有v042的BHE2结束确认。因此只验收本次通知及已捕获字段，不能记作显式结束握手或长期连续网络验收。

没有运行game-pilot、没有转发飞智游戏按键。原装Joy-Con确认过的《空之轨迹2nd》B闪避后接A攻击动作仍未做桥接游戏验证。固定120ms、左160Hz/右320Hz通知不是HD Rumble2保真。

## 当前设备和后续

Pico保持BOOTSEL。旧v040程序区在测试前后均与已核验镜像比较通过；本次固件按设计把新捕获写入0xf0000日志槽，不能称全Flash未变。原MicroPython全Flash备份和此前各阶段快照均私密保留。

监听已退出，飞智输出已停止，原厂配置一致。iPhone USB和电脑专用2.4GHz热点保持开启，不需要换接口或新硬件。

下一步先准备并验证v042在真实主机上的输入转发和显式结束收尾，再推进游戏闭环。若需安装v042 Flash，要先保留当前完整Flash（含本次日志）、重新检查实际凭据构建的镜像边界与恢复材料；不能套用旧v040安装器的固定哈希。
