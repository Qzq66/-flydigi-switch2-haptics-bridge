# Windows成功连接协议对照：准备状态

目的：对照Windows能连接而Pico认证失败的差异，先获取配对/服务发现/输入证据，不发震动、不猜输出报告。

## 本机只读盘点

蓝牙适配器为英特尔USB设备，WPR可用，检查时没有WPR录制。未在标准路径找到Wireshark、USBPcap或BTVS；Windows Kits Testing目录存在，未发现BTVS/BTETLParse。初次受限查询服务/日志被拒，后续提升权限仅只读查询成功；未安装组件或修改设备。

已下载[微软官方BluetoothStack.wprp](https://github.com/microsoft/busiotools/blob/master/bluetooth/tracing/BluetoothStack.wprp)到private，SHA256为d5cc4248be2f0b17e6f83ebc9d62f72e9824817cfff40c34bb47f23c5efb322d。`wpr -profiles`识别成功，未启动捕获。

EtwLogSensitiveData、SimplePairingDebugEnabled、SmpDebugEnabled均未设置（默认）；不启用这些设置。微软[BTVS说明](https://learn.microsoft.com/en-us/windows-hardware/drivers/bluetooth/testing-btp-tools-btvs)明确指出Full Packet Logging可能包含密钥/HID数据，Debug Mode会开启调试配对，本次都不使用。

## 具体采集候选

`work/capture_windows_bt_reference.ps1`使用官方Light内存模式、独立WPR实例，最多120秒，支持private目录下stop.request提前收尾，只停止本次实例。原始ETL、设备身份和主机连接信息全部private，不上传仓库。没有Pico命令、马达命令、注册表修改或驱动安装。

用户准备后才开始采集，看到CAPTURE_READY再开启电脑蓝牙，用Windows正常配对xinput蓝牙模式手柄；成功后确认按键/摇杆响应，保留时间点。不清除其他设备绑定，不操作Switch。重新配对可能让手柄记录电脑绑定，Pico保持BOOTSEL。

采集成功仅表示获得ETL，不等于解码成功或协议打通。默认日志可能省略敏感或较长HID包。可先用现有tracerpt/事件元数据分析配对状态；如需BTETLParse或Wireshark解析，另行说明具体组件，不自动安装驱动。无法解码或数据不全必须标明缺失，不拿普通事件日志代替HCI证据。

## 对照目标

依次核对Windows实际IO/OOB/AuthReq、SSP/SC协商、确认/密钥交互、认证及加密成功、实际SDP服务与报告描述符；再读取按钮输入报告的结构。标准流程复用现有栈，只有确需厂商私有格式时再研究。不得将Windows普通震动或USB私有0x57包推断成蓝牙精细波形支持。

资料：[微软采集流程](https://github.com/microsoft/busiotools/blob/master/bluetooth/tracing/readme.md)、[Wireshark蓝牙采集说明](https://wiki.wireshark.org/CaptureSetup/Bluetooth)。后者指出新版etwdump支持Windows HCI日志，是后续可选解析路径，当前未安装或验证。

## 首次启动未成功；用户随后已连接

首次WPR入口未输出CAPTURE_READY即结束，result=INCOMPLETE，start.txt为空，异常信息未保留下可判读原因。未取得ETL，不得视为成功握手证据。随后提升权限只读查询独立实例和全局状态，均确认WPR is not recording；没有残留采集，也未自动重试。

用户随后说明已连接。保持连接，只读查询目标地址匹配的Present PnP节点：发现3个节点，其中Bluetooth 2个、HIDClass 1个；Classic服务UUID为00001124-0000-1000-8000-00805F9B34FB（HID）和00001200-0000-1000-8000-00805F9B34FB（PnP Information）。这是Windows枚举出的目标服务和HID节点，不是握手包或输入/输出报告，仍不能据此解码蓝牙精细震动。

v2采集候选`work/capture_windows_bt_reference_v2.ps1`改为显式调用System32/wpr.exe并分别收集标准输出、错误输出、退出码和完整异常，保留失败旧入口与证据。语法检查通过；新进程调用函数仅执行-status只读验证，未再开启录制。首次失败原因仍未证实，不能把入口修正当作已解决捕获故障。

下一次必须先看到CAPTURE_READY才安排一次重新连接/配对；暂时不要取消当前成功连接。先确认当前A/B与摇杆是否可用，再确定是否需要完整重配对，避免无信息增益地重复操作。Pico保持BOOTSEL，不发震动，不修改持久马达配置。

## v2取得明确权限错误

用户确认Windows蓝牙A/B和摇杆正常。v2仅尝试开始捕获即停止，原始错误为`Access is denied`，Profile Id=`BluetoothStack.Light.Memory`，HRESULT=`0x80070005`。本次没有CAPTURE_READY或ETL，不得记为已抓到协议。当前进程Windows管理员令牌检查为false；沙箱外执行权限不等于Windows UAC提升。此错误来自WPR/Windows，不是自动审批拒绝或手柄协议错误。

准备了固定本地入口`work/windows_bt_reference_uac.ps1`：要求管理员令牌，调用已审阅v2脚本，限时120秒并将状态和ETL只存private。不安装驱动、不改注册表、不接触Pico、不发送震动。尚未通过UAC运行，需用户确认Windows提升后才开始。保持当前手柄连接，先验证采集真正启动，不立即删除配对或重新配对。

## 当前停止点：用户选择只保存进度

用户明确选择“暂不提升权限，只保存进度”。未弹出UAC、未再次启动捕获、未改变蓝牙连接或配对，未操作Pico。Windows A/B与摇杆正常是用户已确认的成功输入基准；配对握手和报告原始数据仍未采集，不能宣称已逆向完成协议。

下次恢复先确认是否愿意运行上述固定UAC入口；没有新确认不提升权限或启动录制。采集真正输出CAPTURE_READY后才提示手柄操作。暂不需要重新配对、清密钥、刷固件或游戏测试。Pico最后已验证状态为BOOTSEL，隔次恢复仍需重新确认实际状态，不能假定设备未发生变化。
