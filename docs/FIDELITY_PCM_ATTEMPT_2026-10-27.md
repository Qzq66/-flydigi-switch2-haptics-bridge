# PCM摘要主机候选：首次预检未启动

2026-10-27，试次20261027-221301。候选冻结清单及计划一致，原热点/iPhone USB正常、Pico BOOTSEL可见、Steam退出。实际完整Flash验证匹配41代，SHA256为41ffb629aa573db8ff8669241b19b5de4f9fd550ccacfa327501c0815948c92b。

输入预检报告为CANCELLED_OR_TIMED_OUT，manual_started=false、transitions为空、motor_commands=0、configuration_commands=0。未收到开始点击，故父程序以Actual PC button press/release precheck failed结束，保留INCOMPLETE。没有进入新监听、换接或震动输出，也没有新PCM提交摘要；不能算作硬件PCM摘要验收。

无cleanup_error，原41代计划仍有效；若设备未普通上电，保持电脑BOOTSEL即可重开真实A/B按下松开检查。已询问用户是否方便立即点击窗口，等待回复；不得绕过输入活性门槛。若用户未看到窗口，应先定位显示问题，不自动反复运行。

证据：FIDELITY_GAME_RUN_20261027-221301.json及private/fidelity-game-pcm41-console-20261027.txt。此次实际物理核验通过不替代后续同轮Flash/PCM/人工联合验收。资料仅本机。

后续：用户确认方便后已完成221627重试。PCM提交专项通过，整轮因停止后心跳故障保留INCOMPLETE；完整回读及当前42代见FIDELITY_PCM_RUN_2026-10-27.md。
