> 历史阶段记录；当前状态以仓库 docs/HANDOFF_2026-10-22.md 和 docs/STATUS.md 为准。路径及设备序号已脱敏。

# Pico直连接口与键鼠排查

日期：2026-10-22（中国时间）。

## 结论

当前接法已通过短时复测：Pico接电脑直连USB口，飞智接收器移到扩展坞。用户确认手柄正常，Pico从BOOTSEL进入最小RAM固件、再恢复原有MicroPython的整个过程中，键盘和鼠标一直正常。

当前连接可继续用于开发，但尚未确定之前键鼠失灵的根因。此次同时改变了USB连接路径和启动方式，没有做原故障端口的受控对照，不能认定已排除供电、线材、集线器、驱动或固件运行状态等因素。

## 只读基线及日志

Pico未连接时记录41个HIDClass、6个Keyboard、7个Mouse、13个USB类设备，状态均OK；没有Pico USB设备。数量包含复合设备的逻辑接口，不代表外设物理数量。

近期System日志出现10:10左右的WUDFRd驱动警告和启动信息，但没有足够证据把这些事件与之前的Pico插入及键鼠失灵对应起来，不作因果归因。

完整USB属性采集明显较慢。pico-usb-diagnostic-20261022-115715.json的设备列表采于Pico接入前，属性查询及写出时间在后，不能将文件时间当作所有设备的同步快照；其中相对过滤基线多出的设备也不能一概视为刚接入。最终状态另取3项指定属性记录，避免混用。

## 本轮实测

1. 用户将飞智接收器移到扩展坞，再按住BOOTSEL将Pico接入腾出的直连接口。用户确认键鼠及手柄正常。
2. picotool只读查询确认RP2350 A4、QFN60，boot type为bootsel。显示MicroPython程序信息是读取Flash内程序元数据，不代表当时已运行该程序。
3. 核验此前RAM固件UF2的SHA-256为FD18428EFF9FBADC972F359F31F233FDDA92873D9CCB897B6680E8836BEE155F，使用picotool load -v -x加载并校验SRAM成功。
4. RAM固件枚举为COM12。100次独立随机标记USB请求全部匹配。主机往返时间最小0.389 ms、平均0.473 ms、最大1.738 ms；这不是游戏输入或物理马达延迟。
5. 只读JEDEC仍为EF4016，SFDP密度仍为4194304字节。
6. 执行REBOOT，恢复原有MicroPython，USB串口COM11状态OK。
7. 用户明确确认整个切换过程中及当前键鼠一直正常。

没有执行Flash擦除/编程、写板上文件、启用无线、控制外部GPIO、修改Windows驱动或禁用USB设备。本轮也没有向手柄发送震动或配置设置命令。未对全部Flash重新做逐字节比较，不能额外声称全盘哈希不变。

## 记录

- pico-usb-baseline-20261022.json：Pico拔出时的过滤设备基线。
- pico-usb-system-events-20261022.json：近期相关System日志片段。
- pico-bootsel-direct-device.json：BOOTSEL接口身份。
- pico-native-direct-port-test.txt：本轮RAM固件及100次请求结果。
- pico-direct-final-state.json：恢复MicroPython后的Pico、飞智USB位置与键鼠状态。

下一阶段准备Switch设备端识别固件；Switch 2实际识别、握手和原生震动接收均尚未验证。此处不把电脑CDC通信通过当作Switch 2兼容性通过。
