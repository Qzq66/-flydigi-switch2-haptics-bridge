# 八爪鱼 6 官方帮助文档核对

核对日期：2026-10-21。通过 Safari 实际打开页面并点击子文档读取；搜索工具返回的空白 HelpLook 页面不代表原文为空。

## 连接与接管

连接指南：https://help.flydigi.com/docs/er-lian-jie-zhi-nan-CICi

- 官方说明：XInput 模式通过有线／接收器连接后，在空间站高级设置开启“允许第三方应用接管映射”，用于 Steam Input／reWASD。
- 开启后，飞智自身映射服务不再工作，改键、体感等由第三方软件负责。不能把开关当成完全无副作用的通用兼容选项。
- 官方明确八爪鱼 6 没有接收器／有线 DInput 模式。蓝牙 DInput 是另一条连接路径。
- 文档提供内置 Switch 模式的有线／无线连接方法，但没有据此证明完整 NS2 Pro／HD Rumble 2 保真输出。

对本机诊断：官方接管说明与实测状态字段为 0 相符，但仍需开启后复测，不能只凭状态字段断言无线正常、输入流已验证或所有 Mac 游戏兼容。

## 官方触觉边界

FAQ：https://help.flydigi.com/docs/chang-jian-wen-ti-tS7J

- 触觉反馈排障部分说明：低于 20% 电量时，左右握把与左右扳机马达停止输出。
- 该部分同时说明 FlashPlay／蓝牙模式不支持震动反馈，使用有线或 2.4 GHz 接收器，且只支持单手柄连接。
- 该结论应放在本文 X-Haptics／Engine 触觉排障上下文中，不外推为所有 Switch 蓝牙协议或未来固件永远不能震动。但当前不能把八爪鱼蓝牙音圈输出作为已有能力规划。

## 网页配置与运行引擎

进入空间站：https://help.flydigi.com/docs/jin-ru-PC-kong-jian-zhan

深度自定义：https://help.flydigi.com/docs/copy-san-shen-du-zi-ding-yi-fei-zhi-kong-jian-zhan

音频触觉：https://help.flydigi.com/docs/AI-suan-fa-jia-chi-xia-de-yin-pin-chu-jue%C2%A0

- 官方提供网页空间站，XInput 有线／接收器连接后可短按 FN＋LOGO 打开网页入口。
- 网页配置界面无需常驻，但音频触觉 Engine 需要运行。网页存在不等于完整触觉引擎支持 macOS，也不能直接在 Pico 运行。
- 文档说明 AI 全局音频模式会响应电脑其他音频；游戏适配路径可以针对游戏进程音频。这些与本项目主机原生触觉协议转换应分开讨论。

## 项目调整

继续优先评估八爪鱼 USB／原装接收器输出。首轮马达测试确认电量高于 20%。第三方接管设置与厂商输入初始化分别验证。官方网页配置可作为后续检查入口，但尚未实测本机浏览器能否连接及是否提供该开关。未安装引擎、未更新固件、未修改系统安全设置或手柄设置。
