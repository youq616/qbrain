# Qbrain

Windows原生C++20 / PowerShell记忆与知识库，默认SQLite + FTS5。
应用不需要Docker、WSL或Python服务；可选评测工具需要Python。

## 最新源码：N47Z原子批量回执管理

新增fact usage-batch-preview/apply，支持同一来源最多32条回执、8个事实的只读预览、
快照绑定上报/撤回和整批回滚。重复项明确显示为无需修改；发生实际变更后须重新
预览，不能自动重试旧批准。调用方自有事务不会被接管，预览也不授予写权限。

Windows/Linux各组89端到端检查、18/41直接C++事务检查、原60组和继承回归完成。
额外参考账本24轮实际MCP对照通过。[当前状态](CURRENT-STATUS.md) ·
[使用说明](docs/integration/USAGE-BATCHES.zh-CN.md) · [本人分离自审](docs/nodes/N47Z-HARD-AUDIT.md)。
源码还包含N47Y统一完整性与MCP分页修复。两阶段均未改变存储schema、默认权限、
Hook或安装器。[回执完整性说明](docs/integration/RECEIPT-INTEGRITY.zh-CN.md)。

## 当前公开下载仍为N47X

[windows-current-preview-b810d689](https://github.com/youq616/qbrain/releases/tag/windows-current-preview-b810d689)。
选择qbrain-windows-x64-n47x-preview.zip并核对同版SHA256SUMS、START-HERE与PROVENANCE。
4,327,611字节、27文件；SHA256：
`c517582c1ea0e0795e881155edd4d34288e3a002dc3bc7657dafcb96a1eb8b4d`。
该固定b810构建包含N47S–N47W能力，不包含N47Y/N47Z后续源码变化。旧资产/tag不变。
[该版本安装升级说明](docs/integration/CURRENT-PREVIEW-N47X.zh-CN.md)。仍为未签名开发预览。

## 使用与未完成边界

[单条上报撤回](docs/integration/FACT-USAGE.zh-CN.md) ·
[分页审计](docs/integration/FACT-USAGE-AUDIT.zh-CN.md) ·
[模型对照](docs/integration/MODEL-COMPARISON.zh-CN.md) ·
[桥接诊断](docs/integration/TRANSPORT-DIAGNOSTICS.zh-CN.md)。

回执是调用方声称使用，不证明模型消费或事实为真；不会自动改变排序/画像/衰减。
真实客户端、模型质量/费用、PG新模块对等、语义确认、完整ACL/DLP、规模性能、
签名和稳定版终验仍有未完成项，Issue40根因未知。[完成路线](docs/COMPLETION-ROADMAP.md)。

构建使用scripts/build-cl.ps1及scripts/build-tests-cl.ps1，只有同轮生产构建成功且
源码未变才使用-SkipProductionBuild。新增批量C++测试是独立CMake目标，不能只跑
旧测试套件就声称覆盖。确需本机任务时遵循[单提示词交接](LOCAL-AGENT-HANDOFF.md)。
[LICENSE](LICENSE) · [规范清单](docs/OPS-PARITY-LEDGER.md)。
