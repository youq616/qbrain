# Qbrain

## 最新源码 N48P：PostgreSQL 分层上下文

现有 context list/read/summary 和 MCP 分层读取补齐 PG 路径，支持版本绑定的原文分页、
提取式／显式授权的模型摘要，以及页面变化后的派生缓存清除。SQLite 仍默认。
[使用说明](docs/integration/POSTGRES-LAYERED-CONTEXT.zh-CN.md) ·
[审核](docs/nodes/N48P-HARD-AUDIT.md) · [实际合并 PR58](https://github.com/youq616/qbrain/pull/58)。
固定受测136a4828，不能把新文档提交当成另一次程序构建；未签名开发候选，不自动安装。

Windows 原生 C++20 / PowerShell 记忆与知识库；SQLite 默认，PostgreSQL 显式 opt-in。
无需必需的 Docker、WSL 或 Python 常驻服务。可选评测使用 Python。

## N48O：PostgreSQL 会话记忆模块完成整合验收

现有 `memory capture / extract / read / status / drain / forget` 已补齐 PostgreSQL
路径：完整用户证据、来源与片段去重、独立提取许可、租约、过期过滤和遗忘墓碑保持。
不自动迁移 SQLite，不把助手推断变用户事实。短事务与七个表名解析检查保护发布边界。

固定源码 `504f2825` 完成真实 Windows/Linux PostgreSQL、原生回归、完整源码绑定
及本人分离自审。[当前状态](CURRENT-STATUS.md) ·
[中文操作说明](docs/integration/POSTGRES-SESSION-MEMORY.zh-CN.md) ·
[最终审核](docs/nodes/N48O-HARD-AUDIT.md) ·
[实际合并身份 PR57](https://github.com/youq616/qbrain/pull/57)。

**同一 DSN 更换 --brain 标签不形成独立 PG 租户。** source 是逻辑来源，不是RLS。
此模块不代表 fact_store/context/Hook 等全部PG对等，或真实客户端已经消费记忆。

## 已有能力与发行边界

N48M SQLite备份恢复、N48N深度体检、N48F/G/H精确计价与响应导入、N48I费用对照、
N48J执行桥接、N48L质量评估及MCP/OpenCode/回执生命周期保持。原运行实现和旧断言
没有因本轮源码校验补充被重写。新程序是未签名开发候选，不自动安装或开启采集。

PG功能需要可信原生PostgreSQL/libpq及相应VC运行库；小交付包不包含这些依赖。
公开N47X和旧N48K/N48M固定ZIP不被替换，不能用旧包验证新命令。
真实客户端、真实模型/全流程费用、剩余PG、签名、稳定版及Issue40仍独立待验收。
[完成路线](docs/COMPLETION-ROADMAP.md) · [前阶段 README](README-N48N.md) · [LICENSE](LICENSE)。
