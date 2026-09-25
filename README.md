# Qbrain

Windows 原生 C++20 / PowerShell 记忆与知识库，默认 SQLite + FTS5。
应用不需要 Docker、WSL 或 Python 服务；可选评测与开发工具使用 Python。

## 最新源码：N48I 配对任务费用对照

新增 `cost compare`：将两份 N48F 规范化账本按相同任务和声明的共同条件配对，
重新计算完整费用、任务/阶段明细及共享开销。失败、重试、辅助调用均保留；
未知成本、覆盖不完整或主模型/主价格表不一致时，所有差额留空，不挑选有利子集。
金额差和比例使用精确整数/分数，不联网、不读密钥、不打开脑库。

受测源码 `3880dde7` 的验收与本人分离自审见 [当前状态](CURRENT-STATUS.md) ·
[使用说明与六个合成示例](docs/integration/PAIRED-COST-COMPARISON.zh-CN.md) ·
[结果审核](docs/nodes/N48I-HARD-AUDIT.md) · [PR50](https://github.com/youq616/qbrain/pull/50)。
费用更低不代表答案质量相同；调用覆盖、条件和供应商来源并未被认证。

## 已有源码模块

N48H 的 `cost import-stream` 支持三种明确格式的完整 SSE 离线导入；N48G 提供
非流式响应导入。它们返回的 `cost_input` 可原样嵌入新费用对照，不修改原计价算法。
N48E 提供 OpenCode 配置生命周期；N48D 检查隔离 MCP 启动、目录和退出。
N47Y/N47Z 提供回执完整性与只读批量预览、精确批准和整批回滚。
协议握手、回执或合成计价不等于真实模型消费或已证明的费用节省。

## 公开下载仍为 N47X 工程预览

[windows-current-preview-b810d689](https://github.com/youq616/qbrain/releases/tag/windows-current-preview-b810d689)。
选择 qbrain-windows-x64-n47x-preview.zip 及同版 START-HERE、SHA256SUMS、PROVENANCE。
ZIP 为 4,327,611 字节，SHA256：
`c517582c1ea0e0795e881155edd4d34288e3a002dc3bc7657dafcb96a1eb8b4d`。
该包不含 N47Y/N47Z/N48D/N48E/N48F/N48G/N48H/N48I 后续源码功能；本轮不替换发行资产。
仍为未签名开发预览，不拿旧包验证新命令。

## 构建与未完成范围

原生构建使用 scripts/build-cl.ps1 和 scripts/build-tests-cl.ps1。
新直接测试为 tests/cost_comparison 独立 CMake 项目；原 60 组不代替新增目标。
真实后续会话记忆消费、模型质量/费用对照、PG 新模块对等、完整 ACL/DLP、规模性能、
签名和稳定版终验仍有未完成项；Issue40 根因未确定。
[完成路线](docs/COMPLETION-ROADMAP.md) · [单提示词本机交接](LOCAL-AGENT-HANDOFF.md) ·
[上一 README](README-N48H.md) · [LICENSE](LICENSE)。
