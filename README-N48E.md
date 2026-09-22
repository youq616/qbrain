# Qbrain

Windows原生C++20 / PowerShell记忆与知识库，默认SQLite + FTS5。
应用不需要Docker、WSL或Python服务；可选评测与开发工具使用Python。

## 最新源码：N48E完整OpenCode配置生命周期

原生qbrain opencode整合预览、安装、状态、只读审计、卸载、中断恢复与外部编辑
接管。默认只读；执行需匹配当前批准。保留无关JSONC内容，受管条目发生变化时
拒绝接管，不能通过恢复/接管暗中更改许可。此前A/B/C本地模块在本阶段统一集成。
[当前状态](CURRENT-STATUS.md) · [完整用法](docs/integration/OPENCODE-LIFECYCLE.zh-CN.md) ·
[工程自审](docs/nodes/N48E-HARD-AUDIT.md)。

Windows/Linux配置生命周期及原有回归已通过，OpenCode1.18.31实际加载/连接、更新
与卸载有固定记录。该1.x客户端使用--format v1；V2兼容输入会省略阶段超时，不能
声称原生V2验收。宿主补写$schema后需要检查外部差异并明确接管。真实连接不等于
模型已经使用记忆；归属与恢复文件可能含完整私人配置，不能当作脱敏日志上传。

## 已有源码模块

N48D提供明确批准的隔离式MCP运行自检；N47Y统一回执完整性与分页入口；N47Z
提供跨事实批量预览、上报/撤回和事务回滚。原schema及默认权限保持。
[运行自检](docs/integration/ISOLATED-MCP-CHECK.zh-CN.md) ·
[批量回执](docs/integration/USAGE-BATCHES.zh-CN.md) ·
[完整性](docs/integration/RECEIPT-INTEGRITY.zh-CN.md)。

## 当前公开下载仍为N47X工程预览

[windows-current-preview-b810d689](https://github.com/youq616/qbrain/releases/tag/windows-current-preview-b810d689)。
程序包qbrain-windows-x64-n47x-preview.zip，4,327,611字节；SHA256：
`c517582c1ea0e0795e881155edd4d34288e3a002dc3bc7657dafcb96a1eb8b4d`。
取同版START-HERE、SHA256SUMS和PROVENANCE。公开包包含N47S–N47W，不含N47Y/
N47Z/N48D/N48E；旧资产和标签不变，仍为未签名开发预览，不能用旧包验证新命令。
[该版本说明](docs/integration/CURRENT-PREVIEW-N47X.zh-CN.md)。

真实模型记忆消费、质量/费用、长期登录客户端、PG新模块对等、签名和稳定版终验
仍有未完成项，Issue40根因未知。[完成路线](docs/COMPLETION-ROADMAP.md)。

构建使用scripts/build-cl.ps1和scripts/build-tests-cl.ps1；OpenCode直接测试位于
独立tests/opencode CMake项目。旧60组不代表新增独立目标已经运行。
[上一README](README-N48D.md) · [单提示词交接](LOCAL-AGENT-HANDOFF.md) · [LICENSE](LICENSE)。
