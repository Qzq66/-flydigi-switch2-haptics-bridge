# 第四步：平台依赖拆分

2026-10-22，Mac离线完成。十二组301项检查通过，新增25项适配器检查。报告：[MAC_ADAPTER_VERIFICATION_2026-10-22.json](MAC_ADAPTER_VERIFICATION_2026-10-22.json)。原始捕获与旧验证报告保持原样。

## 模块职责

| 模块 | 职责 |
| --- | --- |
| bridge_protocol.py | 纯BHR2校验与协议故障类型 |
| bridge_render.py | 纯解码渲染、缓冲与可注入收集器 |
| bridge_transport.py | 显式构造时创建UDP Client，配置可注入 |
| bridge_network.py | 纯IPv4网络配置、广播与发现来源筛选 |
| bridge_input.py | 纯按键/摇杆转换；旧XInputSource导入兼容 |
| bridge_windows.py | 延迟加载HID owner、XInput读取、Windows计时器 |
| bridge_process.py | 父子进程等待与成功报告判定 |
| bridge_runtime.py | 保留旧导入接口，兼容既有脚本与测试 |

Windows实时入口与回放入口使用新的计时器适配器；计时器获取成功才释放，重复关闭不重复释放。原HID owner的停止、备份和配置核对实现继续使用，没有改变设备命令或波形限制。XInputSource保留断开即故障与唯一槽位限制，并可注入假读取器供离线验证。

默认网络仍为192.168.137.1/24、广播192.168.137.255、端口49724。Client与discover支持NetworkConfig参数；地址/端口不符合约束会拒绝，发现过滤使用IPv4子网判断。这里没有添加命令行自定义网络入口，没有修改热点设置或固件端口；非默认端口只有固件端同步支持才可用于硬件。

纯处理调用方可直接使用 `from bridge_render import Renderer`、`from bridge_protocol import unpack`，不必导入UDP Client或Windows适配器。旧 `from bridge_runtime import ...` 继续可用。

## 离线验证

新增检查覆盖网络默认值/替代子网/来源与端口筛选、非法配置拒绝、假socket绑定和目标端口、计时器成功/失败与成对释放、非Windows硬件入口拒绝、注入XInput的中性/断开/歧义槽位，以及纯协议/渲染模块的依赖边界。全部十二组在意外网络、DLL加载、真实子进程审计拦截下通过。

复现：`python3 tools/run_offline_checks.py`。保存新证据使用 `--report <不存在的路径>`。

## 边界与接续

本次是依赖结构拆分，不是macOS硬件后端实现。没有加载真实DLL、读取手柄、创建真实网络socket、启动受监护硬件进程或改写Pico。Windows接手后需重新验证DLL加载、计时器、HID停止/配置核对、XInput真实输入、热点发现及完整父子进程路径；此前硬件结果不能自动覆盖本次重构。

下一项可以只编译Pico v042，检查Mac构建工具链、4MiB Flash布局及镜像边界，不烧写；硬件暂停继续有效。
