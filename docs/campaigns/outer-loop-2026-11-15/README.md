# 外层空档 campaign — 2026-11-15

状态：**离线完成，hardware_actions=0，network_actions=0**。产品验收不变（INCOMPLETE），
`root_cause` 不变（unproven）。本 campaign 只回答一个问题：试次 165425 那个 8.7016 ms 的
故障 gap 里，没被测量的 8.698 ms 是什么量级、能不能在纯主机上复现。

## 问题从哪来

冻结试次 `docs/FIDELITY_GAME_RUN_20261115-165425.json`
（sha256 `b3f14bda90eeaf1b75c9fe5c36ae20105214c2186c610745007793e239d4de05`）记录：
故障步 `start → tick_entry` 只有 3.6 µs，而前一步 `tick` 结束到本步 `start` 之间空了
8.7016 ms。也就是说 99.96% 的故障 gap 落在"步与步之间"，不在任何已有探针的区间里。
把这段归因给 Wi-Fi、驱动还是 Windows 调度，当时的证据都不支持。

## 方法

`tools/outer_gap_audit.py` 做两件互不依赖的事：

1. **确定性审计**：读冻结报告，重建 31 个步间 gap、22 个派发余量、对应阈值
   （余量 + 4 ms 门禁），校验行单调不重叠、gap 与已测区间不相交、故障迟到与记录一致；
   输出 `measured` / `not_measured` 两张清单。
2. **主机合成探针**：用与产品循环同构的原语（取消文件 `stat`、排空 inbox、
   每 200 次迭代写 1 KiB JSON、`sleep(1 ms)`）跑 `timer_1ms` 与 `timer_unrequested` 两臂，
   测同样的"步间 gap"分布。`tools/test_outer_gap_audit.py` 有 8 个纯合成测试保护审计逻辑。

## 结论

**1. 冻结试次的归因是确定的。** 故障 gap 8.7016 ms 超过全部 22 个局部阈值
（阈值 min 4.0085 / median 6.0706 / max 8.0614 ms），其余 8.698 ms 完全未测量。
这不是"探针算错了"，是"探针没覆盖到"。

**2. 现场循环的节奏是正常的。** 15416 步 / 24.8 s ≈ 621 步/s（1.61 ms/步），
主机同构循环 median 1.632 ms/步。不存在"整体变慢"，只有一次尾部。

**3. 8.7 ms 不是罕见的外部事故，是同一套原语的尾部，而且样本量决定你看到多少。**

| 主机样本 | 臂 | median | p99 | max | >4 ms | >6 ms | >8.7 ms |
|---|---|---|---|---|---|---|---|
| 2 000 | timer_1ms | 1.646 ms | 2.621 ms | 3.813 ms | 0 | 0 | 0 |
| 2 000 | timer_unrequested | 1.628 ms | 2.509 ms | 4.151 ms | 1 | 0 | 0 |
| 20 000 | timer_1ms | 1.632 ms | 2.395 ms | **6.151 ms** | **9** | 1 | 0 |
| 20 000 | timer_unrequested | 1.626 ms | 2.399 ms | **7.373 ms** | **17** | 2 | 0 |

2000 次样本的最大值 3.8 ms 会让人以为"主机很稳"；20000 次样本直接到 6–7 ms。
更关键的是**工作段本身**（stat + 排空 + 写文件）在 20 000 次里最大 4.1 ms / 4.9 ms——
尾部不只是睡醒，写盘和 `stat` 也在里面。

**4. 可靠性算术：4 ms 门禁下 60 秒干净通过的概率很低。**
621 步/s × 60 s ≈ 37 200 次迭代；按实测 p(period > 4 ms) = 4.5×10⁻⁴（timer_1ms）
到 8.5×10⁻⁴（未请求臂），60 秒内预期出现 **17–31 次** 4 ms 级尾部。
现场两次持续试次分别在 24.8 s 和约 19 s 内撞上第一次故障，量级吻合。
所以问题不是"找到那个害人的线程"，而是"**一次 8 ms 的调度尾部不应让协议故障**"。

**5. 计时分辨率对照被污染，已记录。** 本次系统当前分辨率为 0.5 ms
（`NtQueryTimerResolution`：min 15.625 ms / current 0.5 ms / max 1 ms，前后一致），
说明有其他进程持着更细的分辨率；因此 `timer_unrequested` 臂不是"默认 15.6 ms"对照，
证据里同时写了 `resolution_before` / `resolution_after` 和说明字段。

## 这份证据改变了什么

- 不再继续给同一个循环加探针找"元凶段"：尾部就在原语组合里，测得更细也不会消失。
- 下一个技术动作应是**尾部容忍**，而不是平均优化：提前派发 / 预置 deadline /
  让单次 6–8 ms 唤醒抖动不直接变成 `Game PCM scheduler late`。
- 4 ms 门禁与 80 ms 断流保护**未改动**；本 campaign 没有放宽任何约束。

## 边界（不要读过头）

- 主机循环没有 USB、无线、界面负载；因此**仍不能**把现场 gap 归因到 Wi-Fi 或驱动。
- 没有改产品代码，没有接硬件，没有重跑试次；验收状态仍 INCOMPLETE，`root_cause` 仍 unproven。
- 主机臂的 `timer_unrequested` 受其他进程分辨率污染，只能当"同一分辨率下的重复测量"。

## 第二轮（17:40–17:45）：预算分解与唤醒尾部

**6. 故障帧的算术是闭合的。** 用 32 行步级上下文分解最后一帧：
上一次检查距待派发 deadline 只有 **2.103 ms**，实际唤醒延迟 **8.707 ms**，
可容许上限 = 2.103 + 4 ms 门禁 = **6.103 ms**，超出 **2.604 ms**，
得到 lateness **6.608 ms**，与报告记录的 6.6075 ms 一致（误差 0.5 µs）。
859 个已派发帧的门禁余量：median **3.277 ms**、最小 **1.286 ms**——最坏帧只剩 1.3 ms 余量。

**7. 尾部是线程被抢占，不是计时器精度。** 同构循环 20 000 次、四臂对照：

| 臂 | period max | overshoot max | overshoot >3 ms | >5 ms |
|---|---|---|---|---|
| `sleep_1ms`（现行） | 11.17 ms | **10.12 ms** | 5 / 20 000 | 2 |
| `sleep_1ms` + TIME_CRITICAL | 2.81 ms | **1.75 ms** | **0** | 0 |
| 高精度 waitable timer | 6.35 ms | 5.30 ms | 5 / 20 000 | 1 |
| 高精度 timer + TIME_CRITICAL | 2.83 ms | **1.72 ms** | **0** | 0 |

结论：**高精度计时器单独不解决问题**（与早先 2.487 vs 2.016 ms 的结论一致）；
把等待线程提到 `THREAD_PRIORITY_TIME_CRITICAL` 后，10 ms 级尾部整体消失，
最大 overshoot 1.7 ms，远低于故障帧需要的 6.1 ms。

**8. 主机尾部率与现场一致。** 现场约 15 400 步里出现 1 次 >6 ms 唤醒（≈6.5×10⁻⁵/步）；
主机基线 >5 ms 是 2/20 000 = 1×10⁻⁴/步，同一量级。优先级臂是 0/20 000。

**9. 候选已隔离成一个可测的小模块。** `tools/thread_priority.py`：
`with ThreadPriority(TIME_CRITICAL): ...` 进入时提升、退出时必然恢复，
失败会显式抛 `OSError`，不吞异常；不改变 8 ms 网格、4 ms 门禁、80 ms 断流保护。
真实产品接入还需评估 TIME_CRITICAL 的副作用（可能饿死 collector / HID 线程），
所以建议先只包住 armed 窗口并在退出路径强制恢复，必要时退回 `HIGHEST` 档。

## 第三轮（17:46–17:48）：把窗口接进入口并做受控对照

**10. 接入方式是 opt-in，默认零行为变化。** `ObservedGame.tick()` 现在可以通过
`--priority-window`（或子进程继承 `FLYDIGI_PRIORITY_WINDOW=1`）把 `CandidateLoop.step`
包进 `PriorityWindow`；不带这个开关时逐字节等于旧路径。提升只覆盖一次 step，
退出路径（含异常）强制恢复，`summary()` 里会带 `priority_window` 的步数与最大持有时长。

**11. 受控对照直接复现了现场尾部。** 同一循环、同一原语、各 4 000 步 armed，
只差“窗口开/关”一个变量：

| 臂 | overshoot max | >3 ms | >5 ms |
|---|---|---|---|
| 窗口关（现行） | **6.13 ms** | 4 | 1 |
| 窗口开 | **1.61 ms** | **0** | 0 |

窗口关的 1 次 >5 ms 出现在 4 000 步里，与现场 15 400 步 1 次的量级一致；
窗口开时最大只有 1.6 ms，低于故障帧需要的 6.1 ms。

**12. 恢复是逐项验证过的，不是“应该会恢复”。** 真实内核上读回线程优先级：
初始 0 → 关闭臂结束后 0 → 开启臂结束后 0 → 在 step 内故意抛异常后仍是 0；
合成测试另外覆盖了“提升确实发生在动作执行期间”。

## 第四轮（17:49–17:53）：62 代重绑，让入口能对当前基准出计划

**13. 硬阻塞在基准代数，不在策略逻辑。** 冻结策略 `sustained_game_policy_g61.py` 要求
`baseline_generation == 61`，而 11-15 16:54 的试次已把基准推进到 **62**
（`docs/V043_READY_BASELINE_20261115-170226.json`：`baseline_generation=62`、
`physical_full_readback_verified=true`、`outside_journal_unchanged=true`、
`full_flash_sha256=2e2e4a25…`、`firmware_sha256=3f7df348…`）。不重绑，任何试次的
`--prepare` 都会在计划阶段被拒；而放宽代数校验等于让"未验证的 Flash"进流程，禁止。

**14. 重绑只换期望代与证据链，协议预算一个字节没动。** `sustained_game_policy_g62.py`
仍然产出 6 事件 / 60 秒 / 7 500 帧 / 60.25 秒 armed，并把计划绑到 62 的
`full_flash_sha256` 与 `firmware_sha256`；`validate_game_plan` 做全等校验，篡改代数立即拒绝。

**15. 入口同一份代码服务两代。** `dispatch_windows_entry.py --generation {61,62}`：
61 仍走冻结 sha 校验，62 才把 core 的 `GameSession` 换成 g62 的；优先级窗口由
`dispatch_windows_profile_g62.py` 写进计划（`--priority-window` / `TIME_CRITICAL` /
`restore_on_exit` / `scope=armed dispatch step only`），不是命令行临时约定。

**16. 计划本身防漂移。** 计划里绑定 6 个工具的 sha256；改动其中任何一个，
`--prepare` 必须重做，旧计划会被 `validate_game_plan` 拒绝。实测：core62 接受计划、
core61 拒绝、不带授权 `--play` 直接 exit 2（"no device opened"）。

**17. 一次 L0 失败暴露了假用例的隐藏假设。** fake 用例不写 `plan` 文件，而 `run_child`
现在会读它 → 9 个 `FileNotFoundError`。修法是给 `run_child` 加 `generation` 参数：
读不到计划且调用方已提供 core 时才回退 61，否则照常抛错（生产路径不放水）。
重跑 **271 项 PASS / 10.04 s / hardware_actions=0**。

## 试次尝试记录（2026-11-15 17:58–18:00，均未进入 armed 游戏环）

- **17:58:52**：只读预检拒绝。`hotspot_state=Off`、`clients=0`，`ValueError('Original iPhone USB /
  2.4GHz hotspot required')`。`host_flash_write=false`、`persistent_flydigi_commands=0`。
- **17:59:54**：预检通过（`hotspot_state=On`、`clients=0`）后进入运行时：Flydigi enable→disable
  完成（`runtime_disable_ack=true`、`disable_attempts` 一次 `ACK_OK`、`ram_matches` 四区全 true、
  `configuration_unchanged=true`、`identity_matches=true`、`state_matches=true`），
  但发现窗口超时 `TimeoutError('No matching Pico within connection window')`，`child_exit=1`，
  未派发任何帧。
- **18:01 复核**：`clients=1`；`picotool info` 报 "No accessible RP-series devices in BOOTSEL mode"
  → Pico 正在运行固件、已连上热点。两次失败均为**流程性**（热点拉起时序），不是假设被证伪。

- **18:03:17**：Pico 已在运行固件（`clients=1`、`picotool info` 无 BOOTSEL 设备），
  `verify_installed` 的物理 Flash 只读校验失败：`ValueError('Physical Flash does not match the
  v043 installation; keep BOOTSEL')`。未进入运行时启用，`host_flash_write=false`。
- 三次都在 armed 游戏环之前终止；共同原因是**物理状态与入口预检顺序不匹配**：入口要求先 BOOTSEL
  只读核对 Flash、发现就绪后才换接主机，而换接时机此前没有明确到操作层。

## 第五轮（18:04–18:12，修复遥测写盘竞态、回收 63 代、代数改由计划绑定）

**18. 第四次进场不是触觉故障。** 18:05:09 的试次进入了 armed 游戏环，live 47.42 s、派发 3 865 帧，
然后死在遥测写文件：`RuntimeError("Phase writer failed: PermissionError(13, '拒绝访问。')")`。
原因是 `AsyncPhasePath` 用「临时文件 + `os.replace`」，而 Tk 界面线程正拿着同一个文件的读句柄；
Windows 读句柄默认不共享 delete，替换偶发 Sharing Violation。**修复属于遥测层**：写入线程内对
`PermissionError` 重试 8 次、间隔 2 ms，非共享冲突不重试，持久失败仍上报。

**19. 这一轮第一次没有 4 ms 派发故障。** 3 865 帧全部派出，`dispatch_io` 最大 drain 1.676e-4 s、
最大 enqueue 1.3e-5 s；传输 5 454 次轮询 / 4 495 次响应 / 959 次超时 / 最大响应间隔 78.9637 ms
（仍在 80 ms 保护线内）。loop 是被遥测错误终止的，不是被门禁终止——所以这一轮**不能**用来判定
优先级窗口的效果，只能证明它没有引入新的派发失败。

**20. 回收 Flash 到 63 代。** 8/8 校验通过（same_board、candidate_program_unchanged、
outside_journal_unchanged、previous_generation_preserved、fresh_single_generation 等），
`full_flash_sha256=47720be7…`、`previous_generation=62`、`flash_write=false`、仍留在 BOOTSEL。
新基准：`baseline_generation=63`。现场观察：用户感到 3 次震动（与 3 865 帧内的事件数一致）。

**21. 代数不再每代新增一个 policy 模块。** 新增 `sustained_game_policy_current.py`：从 private
安装记录取 `baseline_generation` 与 `installed_snapshot_sha256`，在 `docs/V043_READY_BASELINE_*.json`
中找唯一匹配的 public 证据，并要求 `previous_generation=gen-1`、物理全量回读、日志外不变、
`flash_write=false`、固件摘要一致；同一代若有多份证据且安全字段不一致则拒绝。入口 `--generation`
≥63 时走该 policy，61/62 的历史模块保留不动。63 代计划绑定 **59 个工具**，`g62` 明确拒绝该计划
（跨代混用不可能悄悄发生）。

**22. L0 回归。** 新增 `test_sustained_policy_current`（7 项：按记录绑定、预算不变、JSON 往返、
篡改代数被拒、未知代被拒、适配器绑定优先级窗口、删模块被拒）。总计 **281 项 / 10.68 s / PASS /
hardware_actions=0**。本轮所有改动仍是离线，未打开任何设备。

## 第六轮：提升到底要不要包住 sleep（18:30–18:33）

23. 问题：`priority_window.py` 只包住 `tick()`，而 4 ms 判定发生在 sleep 醒来进入 tick 的那一刻，唤醒时线程仍是普通优先级。`tools/priority_coverage_probe.py` 用同一组合循环（cancel stat、drain、每 200 次 1 KiB phase 写、1 ms sleep、8 ms 网格、4 ms 门禁）跑四臂：normal / tick_only / sleep_boost / armed_boost。
24. 安静窗口结果（每臂 2000 次派发 + 约 2.3 万次唤醒）：

| 臂 | 派发迟到 max | ≥4 ms | 唤醒 overshoot max | collector 唤醒 max |
|---|---|---|---|---|
| normal | 2.863 ms | 0 | 2.764 ms | 2.195 ms |
| tick_only | 3.005 ms | 0 | 5.895 ms | 3.945 ms |
| sleep_boost | 9.251 ms | 1 | 1.583 ms | 3.523 ms |
| armed_boost | 2.645 ms | 0 | 2.088 ms | 3.355 ms |

25. 结论：**逐次 sleep 前后进出 `TIME_CRITICAL` 是反效果**（每毫秒两次内核转换，制造了一次 9.25 ms 停顿）；整段 armed 一次性提升略优于基线（派发 2.645 vs 2.863 ms、唤醒 2.088 vs 2.764 ms），collector 最大唤醒从 2.195 升到 3.355 ms，仍低于 4 ms，但样本里没有 4 ms 事件，**不能宣称“压进 4 ms”**。基线本身在本窗口就没撞到门禁，说明尾部是负载相关的稀有事件。
26. 下一步：不在安静窗口继续调参；负载复现已确认尾部由调度争用驱动（见 27–28），提升只能减半。

27. 负载复现（2 个普通优先级自旋线程，每 1 ms 自旋 + 0.2 ms 让出；每臂 1500 次派发 / 1 万次唤醒）：

| 臂 | 派发迟到 max | ≥4 ms 次数 | 唤醒 overshoot max | collector 唤醒 max |
|---|---|---|---|---|
| normal | 9.335 ms | 10 / 1500 | 10.681 ms | 9.023 ms |
| armed_boost | 5.785 ms | 7 / 1500 | 6.261 ms | 3.582 ms |

28. 结论：整段 armed 提升把最坏值从 9.34 ms 压到 5.79 ms、≥4 ms 次数从 10 降到 7，但**仍然过不了 4 ms 门禁**。也就是说，靠“提升线程优先级”这条路在负载下只能减半，不能消除；4 ms 逐帧门禁与这台机器 125 Hz 的调度现实不兼容。collector 在提升臂反而更好（9.02 → 3.58 ms），因为主线程按时醒来后立刻结束争用，而不是拖长。

## 第七轮：提前唤醒 + 自旋（18:36–18:38）

29. 思路：尾部来自“把最后 1 ms 交给 OS 睡眠”。改成睡到 deadline 前 N ms，最后 N ms 自旋，唤醒尾部被自旋吸收。`tools/spin_wait_probe.py` 在同一负载（2 个自旋线程）下跑 1500 次派发/臂。
30. 结果：

| 臂 | 派发迟到 max | ≥4 ms | 循环线程 CPU | 自旋 max | 收包线程 max |
|---|---|---|---|---|---|
| baseline | 5.078 ms | 7 | 1.0% | 0 | 3.674 ms |
| spin_1ms | 4.883 ms | 1 | 5.2% | 1.000 ms | 7.523 ms |
| spin_2ms | **2.022 ms** | **0** | 15.8% | 2.148 ms | 6.673 ms |
| spin_3ms | **1.270 ms** | **0** | 28.3% | 2.997 ms | 7.528 ms |
| spin_2ms_boost | 6.309 ms | 36 | 3.1% | 1.874 ms | 5.515 ms |

31. 结论：**自旋 2 ms 就能把 1500 次派发全部压进 4 ms**（最坏 2.02 ms），代价是单核 15.8% 与收包线程唤醒最坏 6.67 ms（基线 3.67 ms）；自旋 3 ms 更稳（1.27 ms）但 CPU 28%。**自旋期间再加 TIME_CRITICAL 反而更差**（36 次超门禁），与第六轮“逐次提升有害”一致，应停止用优先级解尾部。
32. 风险与下一步：收包线程最坏 6.67 ms 需要用真实 recv 路径验证是否会丢包/延迟；另外自旋是产品行为改动（发热、功耗），接入前需要单独确认。

## 第八轮：自旋对收包的影响（18:40–18:41）

33. 方法：`tools/recv_spin_probe.py` 在回环 UDP 上让发送线程每 8 ms 发一个带序号包（共 2500 个），收包线程以 1 ms 超时阻塞 recvfrom，主线程跑 8 ms 网格两臂：baseline 与 spin_2ms。
34. 结果：两臂都 **2500/2500 收齐、0 丢包**，收包间隔最大 13.191 ms（baseline）vs 11.667 ms（spin），p99 都是 8.6 ms——自旋没有让收包变差。但同一进程内加进收包线程后，spin_2ms 臂出现 **2/2500 次派发 ≥4 ms**（最大 4.296 ms），baseline 臂 0 次（最大 3.966 ms）。
35. 结论：丢包风险在本轮没有出现；但 Python 同进程的 GIL 争用会吃掉一部分自旋收益。真实收包线程大部分时间阻塞在 recvfrom（释放 GIL），影响应小于本探针；这只能等接线后用一次试次确认，不能靠回环推断。
36. 下一步：把 spin_2ms 接进候选 runner（不改冻结 child 循环、不做全局 monkeypatch），先离线做等价性检查，再等授权试次。

## 第十轮：解剖循环体预算 + 异步 phase 写（19:00–19:11）

184920/185421 两次试次把嫌疑缩到循环体本身：自旋已经把排队尾巴消掉（3168 次自旋、单次最长 2.01 ms），
3181 个已派发帧没有一个迟到 ≥4 ms，但门禁仍在 armed 后约 25 秒以 `Game PCM scheduler late` 停掉。
说明迟到不是发生在 `wait()` 里，而是发生在一次 tick 返回之后、下一次 tick 进入之前——也就是 drain inbox、
0.2 秒同步写 phase、取消检查和收包检查这一段。

29. `tools/loop_probe_session.py`（`FLYDIGI_LOOP_PROBE=1` 开启）：包住 GameSession，每次 tick 记录
    入口迟到（entered − target）、距上次 tick 返回的间隔（= 整个循环体）、tick 自身时长；`ProbePath`
    单独计时 phase 写盘。报告写进 child 的 `loop_probe` 与 `publish_probe`。
30. `tools/async_phase_path.py`（`FLYDIGI_ASYNC_PHASE=1` 开启，默认关闭）：把 phase 写盘移到独立守护线程，
    队列 256，满时退化为同步；PermissionError 重试 8×2 ms；持久失败只记录不抛——避免像 180509 那样
    因遥测写盘把整个 loop 杀掉。它是候选，不是默认路径。
31. 测试拆分：`tools/test_async_phase_path.py` 恢复为入口版 `AsyncPhasePath` 的重试契约（4 项），
    新写盘线程的测试移到 `tools/test_async_phase_writer.py`（6 项）；两组都进 L0。
32. L0：**PASS 320 tests / 10.994 s / hardware_actions=0**，证据 `l0-regression-20261115-191130.json`。
33. 新计划 `windows-entry-plan-g67-spin-20261115-191145.json`（67 代、53 工具、PLAN VALID）；
    190510 的计划因 runner 改动作废并删除。

下一轮的取舍：先只开探针（`FLYDIGI_LOOP_PROBE=1`、异步写保持关闭），让证据决定“要不要异步”。
两个开关同时开会分不清是探针还是写盘线程改变了时间线。

## 证据文件

- `FIDELITY_GAME_RUN_20261115-175852.json`（预检拒绝）与 `FIDELITY_GAME_RUN_20261115-175954.json`（发现超时）
- `FIDELITY_GAME_RUN_20261115-180317.json`（非 BOOTSEL、Flash 校验拒绝）
- `outer-gap-audit-20261115-173245.json`（20 000 次空档审计，第一轮）
- `outer-gap-audit-20261115-173045.json`（2 000 次小样本，保留作对比）
- `step-budget-20261115-1745.json`（故障帧分解，算术闭合）
- `wake-tail-20000.json`（四臂唤醒尾部，第二轮）
- `priority-window-20261115-174747.json`（入口级受控对照，第三轮）
- `windows-entry-plan-g62-20261115-175408.json`（62 代入口计划，已校验）
- `l0-regression-*.json`（最新一次 292 项 / 10.62 s / PASS / hardware_actions=0）
- 工具：`tools/outer_gap_audit.py`、`tools/step_budget_model.py`、`tools/wake_tail_probe.py`、
  `tools/thread_priority.py`、`tools/priority_window.py`、`tools/verify_priority_window.py`、
  `tools/sustained_game_policy_g62.py`、`tools/run_sustained_game_g62.py`、
  `tools/dispatch_windows_profile_g62.py`，各自带 `tools/test_*.py` 合成测试

- `V043_HOST_CAPTURE_20261115-180946.json`（63 代回收，8/8 校验）与
  `FIDELITY_GAME_RUN_20261115-180509.json`（第四次进场，遥测竞态）
- `windows-entry-plan-g63-20261115-181134.json`（63 代入口计划，59 工具绑定，已校验）
- `l0-regression-20261115-181149.json`（281 项 / 10.68 s / PASS）
- `priority-coverage-20261115-183045.json`（四臂提升覆盖对照）、`l0-regression-20261115-183323.json`（292 项 / 10.62 s / PASS）与 `priority-coverage-load-20261115-183400.json`（负载复现）、`spin-wait-load-20261115-183636.json`（自旋对照）、`recv-spin-20261115-184028.json`（收包对照）与 `l0-regression-20261115-184119.json`（301 项 / 10.71 s / PASS）
- `windows-entry-plan-g64-spin-20261115-184800.json`（64 代自旋候选计划，53 工具绑定）与 `l0-regression-20261115-185000.json`（307 项 / 10.64 s / PASS）

## 第九轮：把自旋接进候选循环（18:43–18:50）

离线已经说明：加载下产品循环 1500 次派发有 7 次 ≥4ms（max 5.078ms），把最后 2ms 改成自旋后 0 次（max 2.022ms）；3ms 档 max 1.270ms，但每秒多耗 3ms 的 CPU，2ms 是当前性价比点。本轮把这件事做成可运行的候选，而不是再改探针。

- 生成式复制：`tools/build_spin_child.py` 从冻结的 `run_sustained_game_g61.py` 抽出 `child()` 函数文本，只把结尾的 `time.sleep(.001)` 换成 `wait(game)`，写成 `tools/sustained_game_spin_child.py`。`test_sustained_game_spin_child.Tests` 用 AST 把 `wait(game)` 还原成 `time.sleep(.001)` 后与冻结函数逐节点比对，证明除这一个调用外没有任何差异。
- 候选入口：`tools/run_sustained_game_spin.py` 复用冻结驱动（BOOTSEL 预检、热点门、PC 输入活性、发现、Tk 点击窗口、guardian 全都不变），只把 child 换成自旋版；`FLYDIGI_SPIN_WAIT=1` 才自旋，不设变量时 `wait()` 直接走 `time.sleep(.001)`。
- 计划重出：`windows-entry-plan-g64-spin-20261115-184800.json`（基线 64、full_flash `f185e793…`、53 个工具摘要，含改动后的 `sustained_game_policy_current.py`）。旧的 g64 计划因 policy_current 变化已失效，保留作历史。
- 回归：L0 307 项 / 10.644s / PASS，证据 `l0-regression-20261115-185000.json`。
- 结论边界：这只回答“把最后 2ms 从 OS 唤醒换成自旋，能否让派发不再撞 4ms 门”——它是候选，不是修复；无线、Pico 固件、门禁常数都没动。真正的未知变成：自旋窗口之外若还有 tick 自身的工作，2ms 是否够。

## 下一步（需要单独授权才动硬件）

离线证据已经闭合到“入口级单变量对照 + 62 代计划可出”。现在唯一剩下的变量是现场：
armed 窗口内 overshoot 是否也从 6–10 ms 收敛到 2 ms 级，以及 collector / HID 线程是否
被 `TIME_CRITICAL` 饿死。一次试次的命令形态（未授权时立即拒绝、不打开设备）：

```text
set FLYDIGI_SPIN_WAIT=1 && python tools/run_sustained_game_spin.py --play docs/campaigns/outer-loop-2026-11-15/windows-entry-plan-g64-spin-20261115-184800.json \
  --picotool <pico-tools>\picotool.exe
```

`play()` 会先做只读预检（冻结 sha、实际 Flash 代数 62、热点、A/B 活性、ready 证据），
任一项不符即中止，不自动重试、不写 Flash、不改原厂配置。试次只加 `--priority-window`
一个变量；若观测到掉帧或输入批次延迟，退回 `HIGHEST` 档重测，而不是放宽任何门禁。

## 第十一轮（19:24–19:36）热点凭据漂移与板子不再上线

34. 19:07 的 190744 与 19:02 的 190258 都没进 armed：phase 停在 DISCOVERING，热点 clients 恒为 0。
35. 热点凭据四方核对（header / 保存的 xml / 当前 AP / 固件字节）现已一致：`tools/verify_hotspot_credentials.py` 输出 `PASSED_HOTSPOT_MATCHES_FIRMWARE`，证据 `docs/CAMPAIGN_HOTSPOT_DRIFT.json`。
36. 漂移来源是机器上两份项目副本各带一套网络配置（53E0 与 F470）。项目 private 已同步为固件里的 53E0，旧版留作 `*.f470-20261115.bak.*`。
37. 凭据一致后板子仍未上线：插在 PC（非 BOOTSEL）与 Switch 上，clients 都是 0；PC 侧 `VID_2E8A` 无任何设备，Switch 无 USB 接入提示；BOOTSEL 下可正常枚举并跑 `picotool`。
38. 判定：不是网络凭据问题，而是板子的应用固件在这几次插拔后没有启动（或在启动早期挂掉）。下一次硬件动作的第一步应是只读读回 journal 与整片 Flash 摘要，确认它是否启动过、是否有中止记录，再决定是否需要重写同一份已验证镜像（需单独授权）。

## 第十二轮（19:36–20:00）只读审计与日志区恢复

39. 19:40 只读审计：`picotool verify` 对 67 代基准整片不一致，差异只在 `0x100e0000` 起的日志区；程序区 `0x10000000–0x100e0000` 的 sha256 与基准完全相同（`2dae6a6a…323b6e`），日志记录计数 67→71，说明板子在 18:57 之后又启动过 4 次。
40. 19:45 经用户授权只恢复日志区 128 KiB（备份 `work/journal-before-restore-20261115-194515.bin`，切片 `2a76a7c2…`），未动程序区；恢复后整片 verify 重新通过，板子与 67 代基准逐字节一致。
41. 19:56 决定性对照：Pico 插在电脑上枚举为 `USB\VID_057E&PID_2009`（`BPCAP-RP2350-LOCAL-043`，NS Pro 手柄身份），Steam 能识别 → 板子、固件、USB 栈全部正常。
42. 但热点 `clients` 在以下四种接法下都是 0：电脑直插、纯充电头供电、拓展坞接主机底部 C 口、直插底座 USB-A；手机能在 Wi-Fi 列表里看到 `PicoBridge-Test-53E0`，AP 参数（SSID/32 位密钥/WPA2/2.4G）与固件内嵌字符串一致。
43. 主机打开“更改握法/顺序”看不到 Pico 被识别为 Pro 手柄。结论：不是凭据、不是固件完整性、不是热点广播；卡点是**主机侧没有完成对 Pico 的 USB 注册**，而 Wi-Fi 只在注册之后才起来。18:54 那次能连，是当时注册成功。
44. 下一步（未执行，需现场）：换底座另一个 USB-A 口与另一根线；若主机仍不认，用 BOOTSEL 只读读回日志区，看这次主机插拔有没有写入新的启动记录，以区分“没通电”与“通了电但没被枚举”。

## 第十三轮（20:02–20:15）回滚 v042 与主机不枚举排查

45. 经用户授权回滚：先 `picotool save -a work/before-rollback-v042.bin`（sha256 `66CB50A3…D7FAF`），再 `picotool load build\pico-v042-live-flash\pico_pro_capture.uf2 -x`；重启后电脑识别为 `BPCAP-RP2350-LOCAL-042`，固件在跑。
46. 三个镜像的身份字串一致：v040/v042/v043 都是 `VID_057E:PID_2009`、`BPCAP-RP2350-LOCAL-0xx`、内嵌 `PicoBridge-Test-53E0` + 同一 32 位密钥。因此“早期版本能被认出”不是身份差异；刷回 v040 也不会改变枚举结果。
47. 主机侧排查：主机重启后“更改握法/顺序”仍无 Pro 手柄；`Pro 手柄有线通讯` 已确认为开；拓展坞接在主机顶部 USB-C 口（与 18:54 成功时同一通路）。
48. 拓展坞对照：把拓展坞改接电脑、Pico 插在拓展坞上，电脑立刻认出 `BPCAP-RP2350-LOCAL-042` → 拓展坞供电与数据链路正常，问题在主机对设备的接受，不在板子、线、坞。
49. 板子无 LED，无法直接观察供电；热点 `clients` 在主机上始终 0，Wi-Fi 未启动。当前固件为 v042；v043 的 67 代整片可随时写回。
50. 下一步（未执行）：① 把 Pico 插在拓展坞上再**重启主机**（让主机在启动阶段枚举它）；② 找 USB-C 转 A 的转接头，把 Pico 直接接主机顶部 C 口，绕过拓展坞；③ 若仍不认，用 BOOTSEL 读 v042 日志区，看主机插拔期间有没有写入启动记录。
