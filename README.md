# Qbrain

Windows 原生 C++20 / PowerShell 记忆与知识库。SQLite 默认，PostgreSQL 显式启用；
不要求 Docker、WSL 或 Python 常驻服务。Python 仅用于可选评测和开发验证。

## 最新模块 N48R：PostgreSQL Hook 接入

Hook 可以连接已有 public/UTF8/v13 PostgreSQL 库，不再要求同名本地 brain.db。
空库、错误连接或未知版本不初始化、不迁移、不回退 SQLite。结构化事实与普通会话记忆
在同一个自有只读快照中组合；撤回内容不能通过普通记忆通道复活，读取结束后才采集。
PG 普通记忆去重绑定有效数据库描述，切换数据库不会错误沿用另一数据库的去重结果。

原运行候选45a23853完成双平台完整资格验证；补充a4acb118完成新鲜Windows/Linux实际PG
和独立进程检查。本轮另完成本地回归、ASan/UBSan及原始工件源码/输出复核。
[当前状态](CURRENT-STATUS.md) · [中文说明](docs/integration/POSTGRES-HOOKS.zh-CN.md) ·
[分离自审](docs/nodes/N48R-HARD-AUDIT.md) · [结果](docs/nodes/n48r-evidence/RESULT.json)。
实际合并身份见 [PR60](https://github.com/youq616/qbrain/pull/60)，文档提交不冒充程序构建。

N48O会话记忆、N48P分层上下文、N48Q结构化事实/生命周期/回执继续保留。
默认采集和MCP写许可不扩大；使用回执和Hook返回都不认证真实模型消费。

## 数据和发行边界

**同一 DSN 更换 --brain 名称不是独立 PG 租户；source 不是 RLS。**
数据库、角色、TLS与备份应独立配置；测试脚本只用于专门的一次性数据。
程序未签名，需要可信libpq依赖和匹配的Visual C++ x64运行库；不是免依赖安装包。
没有替换旧固定ZIP或公开Release，没有自动安装或操作用户电脑。
真实客户端消费、代表性模型质量及全流程费用、其余既定功能、完整DLP/RLS、
签名稳定版和Issue40仍独立待验收。N48R完成不代表整个项目结束。
[完成路线](docs/COMPLETION-ROADMAP.md) · [上一README](README-N48Q.md) · [LICENSE](LICENSE)。
