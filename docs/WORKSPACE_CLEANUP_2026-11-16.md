# 工作区整理记录：2026-11-16

本次仅整理目录、索引和可再生成产物，没有运行硬件脚本、修改固件或保护参数、访问设备、烧写、读取私密恢复材料。

## 当前版本

从GitHub取回2af36e77936e335cc6ba81d7d776db7e286457f3：v043两轮120秒基线，取代本机旧v042接续状态。整理不构成新的实机验收。原本地Mac文档提交已被公开历史包含，另留本地分支archive/mac-review-before-cleanup-2026-11-16保存旧提交，未删除历史。

## 本地目录

| 目录 | 用途 |
| --- | --- |
| 工作区根README.md | 只指向github-current，避免使用旧项目状态 |
| github-current/ | 唯一持续开发的Git工作区，路径未变 |
| archive/legacy-workspace-2026-10-21/ | 原外层旧仓库完整归档：旧.git、已提交和未提交资料、旧ZIP/bundle均保留；本地ARCHIVE_MANIFEST.json记录非Git文件哈希 |
| archive/cleanup-evidence-2026-11-16/ | 本地删除清单与占位构建镜像manifest；不是设备恢复包 |
| github-current/build/tooling/ | 保留GCC14.2.1、SDK2.3.1及依赖、CMake/Ninja环境、picotool源码/安装、校验文件和构建日志 |

外层归档不在主仓库内，不上传。需要旧资料时从archive阅读；不要用旧仓库覆盖主项目。整个archive保留原始旧资料，不因整理而保证其适合公开。

## 清理范围

共清除177212117字节（约169.0MiB，按文件逻辑大小统计，不含少量Python缓存）：

- 已解压并安装的Arm工具链及SDK/TinyUSB/CYW43/lwIP/picotool下载归档。
- 两个v042 compile-only构建目录、picotool中间构建目录。
- 仅含公开example参数的compile-only-private目录及项目Python缓存。

删除前核对两份生成镜像SHA256与MAC_V042_BUILD_VERIFICATION_2026-10-22.json一致，确认它们是公开占位参数构建物；保留其manifest副本与原报告。它们不是v042/v043实机恢复镜像。build没有受Git跟踪文件；删除仅限已核对的白名单路径。编译缓存可由源码和保留的工具链重新生成。

保留约1.2GiB工具环境是有意选择：交叉编译器是主要占用，后续编译仍有用途，不将已安装工具链误当垃圾。本次没有全盘清理或删除设备备份。

## 仓库信息整理

README只保留当前基线、日常入口和目录说明；完整文档通过INDEX.md分类，JSON通过EVIDENCE_INDEX.md分类。未移动现有docs报告或handoff源码，因为验收工具、冻结清单、历史链接仍依赖原路径。未更改原始证据、失败反例、许可证或冻结清单，也没有把旧报告覆写为新状态。

本次不生成新的硬件证据。清理后会运行现有硬件拦截离线套件，校验入口与本地Markdown链接；验证结果写在本记录末尾。

验证结果：现有十二组301项离线检查全部通过；五个新/整理入口共172个本地Markdown链接全部存在；外层归档文件逐项SHA256与移动前一致。只改变README并新增三份索引/整理说明，原受跟踪源码和实测证据无修改。
