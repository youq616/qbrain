# Qbrain 当前交付状态

## 已验收：N46F 中文搜索与 HTTP 取消修复

实际测试源码：`c665cb29cb44a6827670b8910b3d6adb568aa2c1`。
[PR #12](https://github.com/youq616/qbrain/pull/12) 的 GitHub 状态决定是否已经合并；
[验证运行](https://github.com/youq616/qbrain/actions/runs/34765651987) 的 Windows、
Server 2022 HTTP、portable、source 和发布任务全部成功。

[下载仓库预览版](https://github.com/youq616/qbrain/releases/tag/cjk-preview-c665cb29)，
选择 `qbrain-windows-x64-cjk.zip`。SHA256：
`d47918eb402692af9c3e4e332bf1f3faf0a86a71f49917dbc549fcf505bc217d`。
完整解压，阅读 `CJK-RECALL.zh-CN.md`。无需在本机编译。
这是未签名开发版，不是整个项目完成或新的真实用户宿主验收。

普通 search 已增加来源隔离的 CJK 连续字串补充；memory_read 仍是原文连续字串匹配，
没有为了命中而放宽证据、来源或遗忘规则。HTTP 最终使用不可变共享会话，所有
认证头、正文、连接、时限和回调仍逐请求隔离。之前不兼容 Server 2022 的池选项
不在最终实现中。系统代理变更后需要重启进程。

48 个原生回归组、72 项 CJK 单测、36 项 CLI/MCP 中文专项通过；两套 Windows HTTP
各 81 项，两个固定 current 进程各 256 次取消且显式关闭缓存。原记忆、Embedding、
队列、Hook、上下文和双 PowerShell 门槛保留。下载证据通过 87 项复核。

[工程复核](docs/nodes/N46F-HARD-AUDIT.md) ·
[机器可读摘要](docs/nodes/n46f-evidence/SUMMARY.json)。

## 未完成：不要把规划当代码

N47 事实图、证据绑定的新存储 API 和冲突管理仍需实际实现，不是本轮交付。
真实 PostgreSQL 对等、完整应用权限审计、真实模型质量/费用、Codex 已登录宿主
闭环以及正式签名发布仍未完成。用户报告的 Claude/Server2022 验收是单独记录，
不替代每个新版的实测，也不等于 Win11/Codex 全部验收。

本地不需要再次导出 N46F 原始源码、配置 GitHub 写权限或安装编译器。
需要新本机验证时，只交接一个提示词；文件必须先发布仓库，按 LOCAL-AGENT-HANDOFF.md
提供固定来源、哈希、使用方法和范围。不让本机并行重写仓库修复。
