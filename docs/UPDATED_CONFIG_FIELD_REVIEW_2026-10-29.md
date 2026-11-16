# 更新后配置字段只读核对（2026-10-29）

用户报告更新手柄驱动。当前配置已private备份，与222645成功备份身份一致，活动slot均0；state首字节0不变，后续一字由1507变7843，语义未证实，不称为配置档切换。global/mapping逐字节一致；lighting长度204变222；motor长度64不变，变化offset33:0→3、35:0→64、44:0→3、46:0→64、55:0→2、56:0→64、57:0→2、58:0→64。已验证grip模式offset23/25不在变化列表。当前motor SHA为a833cbae2d0eac36a993c9fb4e4a9520eedc2ebcebccaf73d66a388be9a79a33。

已有程序没有可靠的变化字段定义，D:/Engine此次有限检索未取得结构说明，不猜测扳机/握把含义，不把驱动更新与差异建立已证因果。旧owner.backup依赖早期runtime-exit-proof的motor SHA，游戏预检于Motor configuration changed处安全退出。不可删除该检查或覆盖旧proof，也不回写用户更新后的配置。

下一步创建独立更新后退出验证：先普通原生短震动/停止/当前配置一致，再研究受限PCM进入退出，用户反馈与停止确认到齐才允许新游戏候选采用新基准。当前未发任何震动或配置写入，Pico保持57代BOOTSEL。