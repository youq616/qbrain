# Qbrain

Windows 原生 C++20 / PowerShell Agent 记忆与知识库，默认 SQLite + FTS5。
运行预编译包不需要编译器、Docker、WSL 或 Python 服务。gbrain / OpenViking
是设计参考，不表示完整功能等价。MIT；保留 LICENSE 和第三方说明。

## 当前源码阶段：N47P 安装可靠性修复已验收

安装器已修复聚合恢复日志大小不一致、回滚前置校验和规划期间外部配置修改保护。
Windows PowerShell5.1/7 各24项快照测试、60项恢复测试及原有安装回归通过；
完整原生60组通过。审核为协调者本人分离工程自审，不是独立子代理或第三方认证。
**本轮仅源码修复，下面N47O下载包内的安装脚本仍不含N47P修复。**
[当前状态](CURRENT-STATUS.md) · [审核](docs/nodes/N47P-HARD-AUDIT.md) ·
[恢复说明](docs/integration/INSTALLER-RECOVERY.zh-CN.md)。

## 当前公开下载：N47O 集成 Windows 预览

2026-09-19：N47M/N47N 已审核修复现在有对应公开下载，不再只有源码。
**[下载 Windows 预览 windows-preview-c26ec5e5](https://github.com/youq616/qbrain/releases/tag/windows-preview-c26ec5e5)**。
选择 `qbrain-windows-x64-reviewed.zip`，先阅读同版本 `START-HERE.zh-CN.md`；
不要误选只含源码的 Source code 压缩包。程序包仍是未签名、非 latest 的 prerelease，
不是整个项目已完成或正式稳定版声明。

[下载校验、升级、项目接入和卸载说明](docs/integration/REVIEWED-PREVIEW.zh-CN.md)
包含可复制 PowerShell 命令。先校验、解压到新目录，不覆盖旧版本；项目安装默认
不采集，采集/事实整理/事实召回需要分别明确选择。不要关闭防病毒或绕过宿主信任。

产品 ZIP：2,117,939 字节；SHA-256：
`ec681a4599bf1b2a90f3848f5bf65b6d6a32e37254f32392d0709c43080b356c`。
包内 EXE SHA-256：`c35fadde8c8356b7243bf0b34cfd5c836bda27bb46da87eddcc79c1031bf05b5`。
原生测试源码为 `c26ec5e512d9ba960b86c9ced5b9b4976b031f2c`。ZIP/EXE/安装脚本保留
原始测试字节，没有重新编译或打包。来源、哈希、两份中文说明和原始验证证据均在
同一 Release；六个资产已做公开前后字节核验及无令牌匿名下载检查。

## 已有能力和本次交付

已有明确授权的会话采集、原话证据与来源、提取/整理、记忆和事实召回、直接反证、
遗忘/归档、分层上下文、项目 Hook、只读诊断及可撤销安装。N47M 修复 memory/context
参数二次解析与选项形状名称误授采集许可；N47N 明确 search 字面参数边界。
N47O 只交付这些已审核修复，不增加数据库迁移、新模型请求或默认采集权限。

```powershell
.\qbrain.exe search --brain my-brain --no-vector --json --query "--brain sentinelneedle"
.\qbrain.exe search --brain my-brain --no-vector --json -- "--brain sentinelneedle"
```

将 `my-brain` 换为实际脑库。字面参数不改变后端排名或等同精确字串查询；
`--no-vector` 不关闭另行请求的 LLM 重排。
[完整语法](docs/integration/SEARCH-ARGUMENTS.zh-CN.md)。

## 剩余路线与验收

核心工程预览已交付，下一步是日常使用验收和产品收口，而非继续只报告节点号。
N47P验收后，**日常可用 v1 还需约 3–5 个实质回合**（含后续集成交付）；
**当前完整扩展路线约 15–25 个回合，包含上述 v1**。这是条件性规划，不是固定
日历或次数承诺。真实宿主、模型、PG、签名条件及新增阻断问题会影响估计。
[详细完成标准、剩余工作和回合估计](docs/COMPLETION-ROADMAP.md)。

真实 PG、完整 ACL/DLP、通用语义合并/冲突推断、使用确认/衰减/画像、更多宿主、
模型质量/费用、实际消费/外发和正式签名仍有未完成项。不要将已有规则当通用
语义理解，将测试工件回读当新真实客户端验收，或将哈希当签名。
[当前状态](CURRENT-STATUS.md) · [N47P 自审](docs/nodes/N47P-HARD-AUDIT.md) ·
[规范操作清单](docs/OPS-PARITY-LEDGER.md) · [PR #33](https://github.com/youq616/qbrain/pull/33)。

## 源码构建与历史

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-cl.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-tests-cl.ps1 -SkipProductionBuild
```

源码构建需要 MSVC；仅同轮生产构建成功且源码未变时跳过重复构建。升级前备份
`%LOCALAPPDATA%\Qbrain\`。Python 是测试工具而非应用服务。真实本机任务遵循
[单提示词交接](LOCAL-AGENT-HANDOFF.md)，不上传密钥或个人聊天。

[N47N README](README-N47N.md)与[N47M 完整能力说明](README-N47M.md)保留历史字节；
其中旧下载状态是历史记录，当前入口以上述新 Release 为准。旧 Release/tag 未覆盖。
[LICENSE](LICENSE) · [第三方说明](THIRD-PARTY-NOTICES.md)。
