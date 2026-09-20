# Qbrain

Windows 原生 C++20 / PowerShell 记忆与知识库，默认 SQLite + FTS5。
应用不需要Docker、WSL或Python服务；可选模型评测工具需要Python3.10+。

## 最新源码：N47Y 完整使用回执校验与 MCP 分页

上报、重试、撤回、汇总和分页现在共享实际类型/ID/版本/时间校验，拒绝损坏的
TEXT/BLOB逻辑别名，不悄悄重复计数或修改数据。另行审核发现并修复了MCP入口
拒绝既有receipt_state/snapshot的问题，健康筛选和连续翻页均有实际进程测试。

Windows/Linux各123完整性检查、普通/-O各72补充检查、原75/71及完整原生60组
完成并核验。模块不改schema/权限/默认行为，不把上报记录当作模型消费证明。
[模块说明](docs/integration/RECEIPT-INTEGRITY.zh-CN.md) ·
[本人分离自审](docs/nodes/N47Y-HARD-AUDIT.md) · [当前状态](CURRENT-STATUS.md)。
**N47Y修复目前在源码，下面的N47X公开包保持原样，尚不包含本次修复。**

## 当前公开下载：N47X 集成工程预览

[windows-current-preview-b810d689](https://github.com/youq616/qbrain/releases/tag/windows-current-preview-b810d689)。
选择qbrain-windows-x64-n47x-preview.zip，并取同版SHA256SUMS及START-HERE说明。
程序包4,327,611字节、27个成员，SHA256：
`c517582c1ea0e0795e881155edd4d34288e3a002dc3bc7657dafcb96a1eb8b4d`。

该包从固定b810源码重新编译，包含N47S模型工具、N47T/U使用记录与审计、N47V
路径保护和N47W桥接诊断。仍为未签名、非latest开发预览，不是稳定版。
[该版本安装与升级说明](docs/integration/CURRENT-PREVIEW-N47X.zh-CN.md)。旧发布保留。

## 操作与边界

[使用上报/撤回](docs/integration/FACT-USAGE.zh-CN.md) ·
[逐条审计](docs/integration/FACT-USAGE-AUDIT.zh-CN.md) ·
[模型对照](docs/integration/MODEL-COMPARISON.zh-CN.md) ·
[路径限制](docs/integration/CASE-SENSITIVE-PATHS.zh-CN.md) ·
[桥接诊断](docs/integration/TRANSPORT-DIAGNOSTICS.zh-CN.md)。

采集和MCP写入仍需明确许可。调用方回执不证明模型实际使用或事实为真；回环测试
不是真实模型效果。Issue40历史超时、实际客户端/模型/费用、PG新模块对等、通用
语义确认/画像/衰减、完整ACL/DLP、规模性能及签名仍有未完成项。
[完整路线与条件性估计](docs/COMPLETION-ROADMAP.md)。

## 源码与历史

构建使用scripts/build-cl.ps1和scripts/build-tests-cl.ps1；只有同轮生产构建成功且
源码未变才使用-SkipProductionBuild。本机确需任务时遵循[单提示词交接](LOCAL-AGENT-HANDOFF.md)。
[上一README](README-N47X.md)保留原字节；[LICENSE](LICENSE) ·
[第三方说明](THIRD-PARTY-NOTICES.md) · [规范操作清单](docs/OPS-PARITY-LEDGER.md)。
