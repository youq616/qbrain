# Qbrain

Windows 原生 C++20 / PowerShell 记忆与知识库，默认 SQLite + FTS5。
应用不需要 Docker、WSL 或 Python 服务；Python 仅用于可选评测和开发工具。

## 最新模块：N48J 模型执行记录费用桥接

已有 N47S 模型 A/B 运行目录可直接用 `model_cost.py export|verify` 生成规范化
账本、覆盖观察和原生 N48I 费用对照，不再手工整理响应里的缓存 Token。
原始计划、请求、回执与响应先核验；失败成本和未知值保留，未尝试位置不伪造成调用。
只统计计划内主请求，不声称全流程费用或质量保持。工具离线运行，不读密钥或答案。

固定候选 `bb5ea5fe` 已通过 Windows/Linux 验证及本人分离自审。
[中文使用说明](docs/integration/MODEL-EXECUTION-COST.zh-CN.md) ·
[当前状态](CURRENT-STATUS.md) · [结果审核](docs/nodes/N48J-HARD-AUDIT.md) ·
[实际合并记录 PR51](https://github.com/youq616/qbrain/pull/51)。

## 已有源码能力

N48I 原生 `cost compare` 对照相同任务的完整账本，保留共享开销、失败和重试。
N48G/N48H 提供非流式与完整 SSE 导入，N48F 提供规范化 Token 精确计价。
N48E 提供 OpenCode 生命周期；N48D 检查隔离 MCP 启动、目录和退出。
N47Y/N47Z 提供回执完整性及只读批量预览、精确批准和整批回滚。
协议握手、回执与合成计价不等于真实模型消费或效果提升。

## 公开下载仍为 N47X 工程预览

[windows-current-preview-b810d689](https://github.com/youq616/qbrain/releases/tag/windows-current-preview-b810d689)。
选择 qbrain-windows-x64-n47x-preview.zip 及同版 START-HERE、SHA256SUMS、PROVENANCE。
该包不含后续 N47Y/N47Z/N48D–N48J 源码能力，本轮没有替换发行资产。
ZIP SHA256：`c517582c1ea0e0795e881155edd4d34288e3a002dc3bc7657dafcb96a1eb8b4d`。
仍为未签名开发预览，不用旧 EXE 验证新命令。

## 构建与未完成范围

原生构建使用 scripts/build-cl.ps1 与 scripts/build-tests-cl.ps1；原 60 组并不
替代新增独立测试目标。N48J 使用既有原生计价，没有改动应用、旧工具或旧测试。
真实后续会话记忆消费、真实模型质量/全流程费用、PG 对等、完整 ACL/DLP、规模
性能、签名及稳定版验收仍有未完成项；Issue40 根因未确定。
[路线](docs/COMPLETION-ROADMAP.md) · [本机交接](LOCAL-AGENT-HANDOFF.md) ·
[上一 README](README-N48I.md) · [LICENSE](LICENSE)。
