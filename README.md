# Qbrain

Windows原生C++20 / PowerShell记忆与知识库，默认SQLite + FTS5。
应用不需要Docker、WSL或Python服务；可选评测与开发工具使用Python。

## 最新源码：N48D隔离式MCP运行自检

新增mcp-check preview/run：明确查看并批准程序指纹，在新HOME和最小环境中检查
初始化、工具目录、ping、正常退出与清理，不调用模型或记忆工具，不传入真实脑库。
只有全部阶段及清理满足条件才报告成功。它不是恶意程序安全沙箱或真实Agent验收。

两平台普通/-O每组172检查、Windows79/Linux76直接检查、原Windows60组与14套
既有进程回归通过；额外25类边界和ASan/UBSan复核完成。审核与使用说明已归档。
[当前状态](CURRENT-STATUS.md) · [用法和限制](docs/integration/ISOLATED-MCP-CHECK.zh-CN.md) ·
[本人分离自审](docs/nodes/N48D-HARD-AUDIT.md)。

## 已有源码模块

N47Y统一使用回执完整性并修复MCP分页入口；N47Z提供最多32回执/8事实的只读预览、
精确批准、批量上报/撤回与整批回滚。单条命令、schema和默认权限保持。
[批量用法](docs/integration/USAGE-BATCHES.zh-CN.md) ·
[完整性](docs/integration/RECEIPT-INTEGRITY.zh-CN.md)。
N48A/B/C的OpenCode配置管理仍是另外未合并工作，不属于当前已接受源码功能清单。

## 当前公开下载：N47X工程预览

[windows-current-preview-b810d689](https://github.com/youq616/qbrain/releases/tag/windows-current-preview-b810d689)。
选择qbrain-windows-x64-n47x-preview.zip及同版START-HERE、SHA256SUMS和PROVENANCE。
ZIP为4,327,611字节，SHA256：
`c517582c1ea0e0795e881155edd4d34288e3a002dc3bc7657dafcb96a1eb8b4d`。
公开包包含N47S–N47W，不含N47Y/N47Z/N48D；旧资产与标签保持原样。仍为未签名开发
预览，不是稳定版。[该版本安装升级说明](docs/integration/CURRENT-PREVIEW-N47X.zh-CN.md)。

## 边界与构建

调用方使用回执不证明模型消费或事实为真；不会自动驱动排名、画像或衰减。真实
Agent加载、模型质量/费用、PG新模块对等、语义确认、ACL/DLP、规模性能、签名和
稳定版终验仍有未完成项；Issue40根因未确定。[完成路线](docs/COMPLETION-ROADMAP.md)。

原生构建用scripts/build-cl.ps1和scripts/build-tests-cl.ps1。只有同轮生产构建成功且
源码未变才使用-SkipProductionBuild。N48D直接测试使用tests/mcp_probe独立CMake
项目；旧60组不代表已运行该新增测试。确需本机时遵循[单提示词交接](LOCAL-AGENT-HANDOFF.md)。
[旧README](README-N47Z.md) · [LICENSE](LICENSE) · [规范清单](docs/OPS-PARITY-LEDGER.md)。
