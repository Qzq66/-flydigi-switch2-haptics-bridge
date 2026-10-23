# 平板热点对照准备，2026-10-22

用户同意使用已有平板2.4GHz热点，不购买串口模块。保留旧v040 Flash，仅加载v042 RAM进行无飞智输出的网络对照。当前尚未取得平板网络的有效时序测量，不能记为改善或通过。

## 代码和本地输入

- v040/v042 bridge_transport.c 的允许电脑IPv4地址可通过本地凭据头 BRIDGE_HOST_IPV4 指定，默认仍为192.168.137.1，没有放开地址白名单。冻结的回滚目录未改动。
- build_pico_snapshot.py 支持独立凭据目录和构建目录，compile-only不能指定真实凭据。v042 RAM可显式选择 --ram-end-bootsel，正常结束/显式复位后回BOOTSEL，不启动保留的Flash固件；默认路径保持原行为。
- 本地GUI只在忽略目录 work/private/tablet-network 保存参数；没有向聊天输出SSID、密钥或会话。密码由用户本地输入；用户确认密码未改变后，允许从该本地文件复用。
- 当前301项离线协议/渲染/适配器检查通过，见 WINDOWS_NETWORK_PARAMETER_CHECKS_20261022.json。RAM构建实际成功，地址在0x20000000..0x2004a600，无Flash写入符号；这不等于硬件联网成功。

## 实际结果和待办

1. 初次电脑网络为2.4GHz信道11，当前协商WPA3-Personal。初次GUI错误地使用Windows网络配置名预填SSID；后续本地比较确认它与真实SSID不一致。该错误已向用户说明并修正为读取实际SSID。固件按WPA2配置；不能仅凭电脑协商WPA3就断言热点不允许WPA2。
2. 首次RAM诊断见 WINDOWS_NETWORK_TIMING_RECHECK_20261022-204326.json：Pico未加入网络，link=-2、IP0.0.0.0，实际测量阶段为空，未输出震动。没有据此认定密码错误。诊断回BOOTSEL成功，全4MiB Flash与测试前快照逐字节verify通过；旧固件和日志未改。
3. 用户表示已改WPA2后，电脑实际连接却变成5GHz WPA2-Enterprise，SSID也与目标热点不同。该连接下的重建产物没有加载到Pico，不能使用。已暂停，等待用户重新连接平板2.4GHz WPA2-Personal。
4. 本地参数工具已增加频段和认证方式检查，不符合时拒绝更新凭据；不再把Windows配置名当SSID。下一轮需重新刷新参数并重建、检查实际连接未变，再运行RAM测量。
5. 当前Pico保持BOOTSEL，Flash旧固件保留；无桥接监听，无飞智输出，电脑原热点未由本轮启用。不要切接Switch 2。平板热点/电脑Wi-Fi连接由用户手动调整，未擅自恢复或更改。

原Flash测试前快照位于忽略目录，含私密固件参数，禁止上传。此文仅保存准备和失败证据，不声称已完成网络优化。

## 用户终止平板尝试，切回电脑热点

用户随后说明电脑显示“无法连接到这个网络”，明确要求使用之前配置的电脑热点。不再要求继续平板或购买串口模块。已调用冻结旧方案的 pico-hotspot.ps1 -BridgeNetwork，返回 HOTSPOT_READY TwoPointFourGigahertz，启动前客户端0。当前选择仍为旧v040 Flash/120ms ±12提示方案；Pico保持BOOTSEL，没有重新刷写，没有监听或震动输出。电脑热点目前为开启状态，尚未解决先前测得的实时延迟；后续在该方案内排查。
