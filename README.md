# Qbrain

Windows 原生 C++20 / PowerShell 记忆与知识库，默认 SQLite + FTS5。
不要求 Docker、WSL 或 Python 常驻服务；可选离线评测使用 Python。

## N48M：原生 SQLite 备份、校验与恢复到新目录

新增 `qbrain backup create|verify|restore`。以明确指定的 SQLite 数据库建立
一致性快照，包含已提交 WAL 数据，排除未提交事务。校验和恢复要求提供创建时
外部保存的清单摘要；恢复只写全新目录，不覆盖活动脑库或更改默认注册信息。

备份是**明文、未加密**的完整数据库，包含全部 source 和数据库内配置。
不包含附件、客户端设置、安装器状态或全局注册文件；当前数据库上限 256 MiB。
这是本地行政操作，不是 MCP 工具、单 source 导出、PG 或完整目录灾备。

受测源码 `d9942612` 已通过 Windows/Linux 原生验证、数据回读及本人分离自审。
[完整用法](docs/integration/SQLITE-BACKUP.zh-CN.md) ·
[当前状态](CURRENT-STATUS.md) · [结果审核](docs/nodes/N48M-HARD-AUDIT.md) ·
[实际合并记录 PR54](https://github.com/youq616/qbrain/pull/54)。

## 已有评测与集成能力

N48L 将同次执行的逐题质量与主请求费用联合评估，正确拒答与实际解决任务分别报告。
N48J 连接模型执行回执与费用；N48I 提供配对账本对照；N48F/G/H 提供精确计价及
非流式/完整流式导入。OpenCode、MCP 和回执生命周期能力继续保留。
原有代码和测试没有为本模块改写，只有早期命令分派与帮助新增入口。

## Windows 交付及未完成边界

N48M 以新的、未签名的 Windows 原生工具包交付，不会自动安装、采集或操作用户脑库。
以前交付的 N48K 固定 ZIP 和公开 N47X Release 不变，它们不含新的 backup 命令；
不要只凭内部 2.0.0 字符串判断版本，以受测源码和可执行文件摘要为准。
[旧候选包说明](docs/integration/WINDOWS-CANDIDATE-N48K.zh-CN.md)。

真实客户端后续记忆消费、真实模型质量/全流程费用、PG 对等、签名、稳定版及
Issue40 仍需独立验收。结构完整性不等于业务语义或来源认证，备份也不替代这些门槛。
[完成路线](docs/COMPLETION-ROADMAP.md) · [上一 README](README-N48L.md) · [LICENSE](LICENSE)。
