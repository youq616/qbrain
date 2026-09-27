# Qbrain

Windows 原生 C++20 / PowerShell 记忆与知识库，默认 SQLite + FTS5。
不要求 Docker、WSL 或 Python 常驻服务；可选评测脚本需要 Python。

## N48K：可运行的 Windows 集成候选

将 N47X 之后的回执、MCP/OpenCode、精确计价及 N48J 模型执行费用桥接整合到
一个独立 Windows x64 ZIP。无需自行编译。它仍是未签名开发候选，不是稳定版，
不会自动安装或授权采集；本轮没有替换旧 N47X GitHub Release。

运行包为 `qbrain-windows-x64-n48k-candidate.zip`，4,890,639 字节、51 个成员。
SHA256：`58d56b7bd7c9a662514e41d20bacb88c68c92bbe3fc380496a09331bf1f5cafa`。
原始完整资格验证通过；另补齐升级前回执保留测试，两个 Windows 运行环境中的
PowerShell 5/7 均验证升级、回退、再次升级和卸载，事实及有效/已撤销回执完整保留。
这不是对真实登录客户端记忆消费或所有 Windows 用户环境的认证。

[实际交付与合并 PR52](https://github.com/youq616/qbrain/pull/52) ·
[外部验收记录](docs/nodes/n48k-evidence/ACCEPTANCE.json) ·
[自审报告](docs/nodes/N48K-HARD-AUDIT.md) · [当前状态](CURRENT-STATUS.md)。
包内构建 MANIFEST 保持原字节；最终验收通过外部记录绑定同一 ZIP，不改包冒充新构建。

## 使用与已有能力

先核验摘要并解压到新目录，再读包内 START-HERE 或
[候选包说明](docs/integration/WINDOWS-CANDIDATE-N48K.zh-CN.md)。保留旧目录与脑库备份。
N48J 提供执行记录费用桥接；N48I 提供任务配对费用对照；N48G/H 导入供应商用量；
N48E/D 提供 OpenCode 生命周期与隔离 MCP 检查；N47Y/Z 提供回执审计与批量处理。
完整原生构建入口仍是 scripts/build-cl.ps1 和 scripts/build-tests-cl.ps1。

真实客户端后续记忆消费、真实模型质量/全流程费用、PG 对等、签名、稳定版和
Issue40 启动超时根因仍须独立验收，不因候选包测试通过而关闭。
[既有路线](docs/COMPLETION-ROADMAP.md) · [本机交接](LOCAL-AGENT-HANDOFF.md) ·
[上一 README](README-N48J.md) · [LICENSE](LICENSE)。
