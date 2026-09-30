# Qbrain

Windows 原生 C++20 / PowerShell 记忆与知识库。SQLite 默认，PostgreSQL 显式启用；
不要求 Docker、WSL 或 Python 常驻服务。Python 仅用于可选评测和开发验证。

## N48Q：PostgreSQL 结构化事实、生命周期与显式使用回执

现有事实 create/attach/promote/read/recall/conflicts/retract/supersede、归档恢复与
生命周期批次，以及显式使用回执和原子批次，已补齐 PG 路径。保留完整用户证据、
来源隔离、预期版本、历史与撤销记录；不自动推断事实、不自动提高 confidence。

受测整合提交 `28d64ae7` 已通过新的 Windows/Linux 原生 PG 验证与 ASan/UBSan。
实际合并身份见 [PR59](https://github.com/youq616/qbrain/pull/59)，后续文档提交不冒充
程序构建来源。[当前状态](CURRENT-STATUS.md) ·
[中文说明](docs/integration/POSTGRES-STRUCTURED-FACTS.zh-CN.md) ·
[分离自审](docs/nodes/N48Q-HARD-AUDIT.md) · [结果索引](docs/nodes/n48q-evidence/RESULT.json)。

N48O 会话记忆、N48P 分层上下文与摘要缓存继续保留。N48Q 不包含 PG Hook 接入，
也不证明真实登录客户端已经使用了记忆。使用回执始终是调用方陈述，不是模型消费认证。

## 数据和发行边界

**同一 DSN 下更换 --brain 名称不形成独立 PG 租户；source 不是 RLS。**
使用真实数据前应分别配置可信数据库、角色、TLS 与备份，不把测试脚本用于生产库。
SQLite 不自动迁移，模型外发仍需单独许可。本模块未修改默认采集或 MCP 写授权。

CI 工件包含固定受测 EXE 和原始测试记录，不是一键安装器或免依赖软件包。
Windows PG 程序需要可信 libpq 依赖及匹配的 Visual C++ x64 运行库，程序未签名。
本轮不替换公开发行或旧固定 ZIP，不自动安装或操作用户电脑。

真实客户端消费、代表性模型质量及全流程费用、剩余 PG/Hook、完整 DLP/RLS、
签名稳定版和 Issue40 仍需独立验收，不能由单个模块通过替代。
[完成路线](docs/COMPLETION-ROADMAP.md) · [上一 README](README-N48P.md) · [LICENSE](LICENSE)。
