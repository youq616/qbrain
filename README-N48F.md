# Qbrain

Windows原生C++20 / PowerShell记忆与知识库，默认SQLite + FTS5。
应用不需要Docker、WSL或Python服务；可选评测/开发工具使用Python。

## 最新源码：N48F规范化Token费用核算

新增原生cost report，离线读取调用方提供的用量与费率，按调用、阶段、费率卡汇总。
支持主模型/嵌入/摘要/抽取/重排费用；普通输入、缓存读、缓存写、输出分别计价，
失败和重试记录保留。精确整数运算、12位小数、缺失项明确未知，不把零与缺测混同。

两平台103直接检查、每模式149进程检查、原生/原有回归与另行Fraction参考复核通过。
这是费用计算层，不是自动用量采集、真实供应商账单或费用节省证明。
[使用和合成示例](docs/integration/TOKEN-COST.zh-CN.md) ·
[当前状态](CURRENT-STATUS.md) · [本人分离自审](docs/nodes/N48F-HARD-AUDIT.md)。

## 已有源码能力

N48E已集成OpenCode项目配置完整生命周期：预览、明确安装、审计、卸载、恢复和
保留外部编辑的接管；固定OpenCode1.18.31加载/连接范围已验收，V1兼容读取不冒充
原生V2引擎验证。N48D提供隔离式MCP运行检查；N47Y/N47Z提供完整性与原子批量回执。
[OpenCode](docs/integration/OPENCODE-LIFECYCLE.zh-CN.md) ·
[隔离自检](docs/integration/ISOLATED-MCP-CHECK.zh-CN.md) ·
[批量回执](docs/integration/USAGE-BATCHES.zh-CN.md)。

## 当前公开下载仍为N47X

[windows-current-preview-b810d689](https://github.com/youq616/qbrain/releases/tag/windows-current-preview-b810d689)。
选择qbrain-windows-x64-n47x-preview.zip及同版说明/校验文件。ZIP4,327,611字节，SHA256：
`c517582c1ea0e0795e881155edd4d34288e3a002dc3bc7657dafcb96a1eb8b4d`。
该包只含N47S–N47W，不含其后源码；旧资产和标签保持。仍是未签名工程预览，
不是稳定版。[该版本安装升级说明](docs/integration/CURRENT-PREVIEW-N47X.zh-CN.md)。

## 构建和剩余工作

原生构建使用scripts/build-cl.ps1和scripts/build-tests-cl.ps1；新费用直接测试使用
独立tests/cost项目，旧60注册组不能代替它。真实模型记忆消费、质量与实际费用、
自动全链路采集、PG新模块对等、语义确认/画像/衰减、ACL/DLP、规模性能、签名及
最终稳定验收仍有未完成项。Issue40根因未确定。[完成路线](docs/COMPLETION-ROADMAP.md)。
[上版README](README-N48E.md) · [LICENSE](LICENSE) · [规范操作清单](docs/OPS-PARITY-LEDGER.md)。
