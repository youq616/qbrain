# Qbrain

Windows 原生 C++20 / PowerShell 记忆与知识库，默认 SQLite + FTS5。
应用不需要 Docker、WSL 或 Python 服务；可选评测与开发工具使用 Python。

## 最新源码：N48H 完整 SSE 用量导入与精确计价

新增 `cost import-stream`：离线读取完整保存的 OpenAI Chat、OpenAI Responses 或
Anthropic Messages SSE，核验身份、顺序和结束状态后，输出互斥 Token 桶与精确费用。
累计用量不重复相加；缺失/null 保持未知；历史总量和缓存下界矛盾整批拒绝。
不联网、不读密钥、不打开脑库，不输出响应正文，也不是账单来源认证。

验收提交 `0227db92` 的三条 CI、六个 Windows/Linux 原生任务通过。两平台各 94 项
直接检查，保留原 543 用例与 187 检查，补充每模式 711 用例及 22 种证据篡改拒绝。
实际合并状态见 [PR49](https://github.com/youq616/qbrain/pull/49)，不将文档收尾提交
冒充构建来源。[当前状态](CURRENT-STATUS.md) ·
[使用说明与合成示例](docs/integration/STREAM-USAGE-IMPORT.zh-CN.md) ·
[本人分离自审](docs/nodes/N48H-HARD-AUDIT.md)。

## 已有源码模块

N48G 提供最终非流式供应商响应导入，N48F 提供规范化 Token 精确费用报告。
N48E 提供 OpenCode 配置完整生命周期；N48D 检查隔离 MCP 启动、目录和退出。
N47Y/N47Z 提供回执完整性与只读批量预览、精确批准和整批回滚。
协议握手、回执或合成计价不等于真实模型消费或已经节省费用。

## 公开下载仍为 N47X 工程预览

[windows-current-preview-b810d689](https://github.com/youq616/qbrain/releases/tag/windows-current-preview-b810d689)。
选择 qbrain-windows-x64-n47x-preview.zip 及同版 START-HERE、SHA256SUMS、PROVENANCE。
ZIP 为 4,327,611 字节，SHA256：
`c517582c1ea0e0795e881155edd4d34288e3a002dc3bc7657dafcb96a1eb8b4d`。
它不含之后 N47Y/N47Z/N48D/N48E/N48F/N48G/N48H 源码功能；本轮不替换发行资产。
仍为未签名开发预览，不拿旧包验证新命令。

## 构建与未完成范围

原生构建使用 scripts/build-cl.ps1 和 scripts/build-tests-cl.ps1。
新增直接测试为 tests/stream_import 独立 CMake 项目；原 60 组不代替新增目标。
真实后续会话记忆消费、模型质量/费用对照、PG 新模块对等、完整 ACL/DLP、规模性能、
签名和稳定版终验仍有未完成项；Issue40 根因未确定。
[完成路线](docs/COMPLETION-ROADMAP.md) · [单提示词本机交接](LOCAL-AGENT-HANDOFF.md) ·
[上一 README](README-N48G.md) · [LICENSE](LICENSE)。
