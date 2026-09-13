# Qbrain

Windows 原生 C++20 / PowerShell Agent 记忆与知识库，默认 SQLite + FTS5。
不要求 Docker、WSL 或 Python 服务。由 `Lordakee/qbrain` 的 MIT 代码继续开发；
gbrain / OpenViking 是设计参考，不是完整功能等价声明。

## 当前已验证开发版：N46F

**[下载 Windows x64 预览版](https://github.com/youq616/qbrain/releases/tag/cjk-preview-c665cb29)**，
选择 `qbrain-windows-x64-cjk.zip`，完整解压。ZIP SHA-256：
`d47918eb402692af9c3e4e332bf1f3faf0a86a71f49917dbc549fcf505bc217d`。

实际测试源码：`c665cb29cb44a6827670b8910b3d6adb568aa2c1`。
[完整原生验证与发布运行](https://github.com/youq616/qbrain/actions/runs/34765651987)
已成功结束；[PR #12](https://github.com/youq616/qbrain/pull/12) 的实时状态决定合并状态。
后续文档提交不改变经过验证的 EXE 和脚本字节。旧内部版本号不足以识别修复范围，
以包内 MANIFEST、源码 SHA 和外部固定摘要为准。历史 `dist/` 不是本批产物。

本轮普通 search 增加中文、假名、韩文连续字串补充，保留全文优先、来源隔离、
删除过滤、去重和稳定排序。memory_read 仍读取经过提取的连续原文字串，不是语义
问答；它的算法没有改变。新增 72 项 CJK 单元和 36 项真实 CLI/MCP 检查通过。

HTTP 最终改用一个不可变共享会话，连接、认证头、正文、回调和时限逐请求隔离；
父对象保留至最终回调。Server 2022 和 Server 2025 的 HTTP 81 项检查及固定取消
对照通过。没有提高句柄增长阈值或关闭 TLS 验证；系统代理变更后须重启进程。

完整 Windows 48 个注册组、原有记忆/MCP/Hook/上下文/Embedding、40 个队列场景
和双 PowerShell 门槛通过。真实 PostgreSQL DSN 用例明确跳过，不计作 PG 验收。
交付回读完成 87 项检查，发布任务核验了上传后字节。包仍未签名。

[当前项目状态](CURRENT-STATUS.md) · [工程复核](docs/nodes/N46F-HARD-AUDIT.md) ·
[机器可读证据](docs/nodes/n46f-evidence/SUMMARY.json) ·
[中文检索语义与免编译专项复测](docs/integration/CJK-RECALL.zh-CN.md)

## 已有能力与边界

会话归档和有原文证据的记忆；采集开关、来源隔离、重试去重、遗忘防恢复；
Claude/Codex 项目级 Hooks、可撤销安装；L0/L1 摘录和单独许可的可选摘要；
L2 原文分页、缓存失效、六工具 MCP；精确有界向量候选、模型标签隔离、
可靠的批量 Embedding 队列、过期结果拒绝和有界锁等待。

**可试用的开发预览，不是全盘开发完成。** N47 事实图和语义冲突处理仍待实现。
新 memory/context 目前仅 SQLite。真实模型质量/费用、全应用 ACL/DLP、
Codex 登录宿主闭环、Win11 正式验收和签名发行没有由本轮完成。
合成事件、有限取消样本和字节/速度基准不是全场景质量或零泄漏保证。

## 使用与数据

升级前备份已有脑库；完整解压同一个开发包，使用其中的安装器。
安装默认只召回，`-EnableCapture` 单独开启该项目本地采集；不会自动开启
Qbrain 模型外发或 MCP 写权限。客户端项目/Hook 信任仍须正常确认。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Install-QbrainMemory.ps1 -HostName Claude -ProjectPath "D:\Projects\MyProject" -Binary ".\qbrain.exe" -EnableCapture
```

Codex 使用 `-HostName Codex`，实际版本和认证/Hook 行为需单独验收。
默认数据位于 `%LOCALAPPDATA%\Qbrain\`；卸载保留记忆与备份。
不上传真实会话、数据库或密钥。不要用固定旧 464045e2 摘要的 N46E 工具装载新包。
[中文安装与卸载](docs/integration/QUICKSTART.zh-CN.md) ·
[完整行为说明](docs/integration/WINDOWS-MEMORY.md) ·
[本地 Agent 单提示词交接规范](LOCAL-AGENT-HANDOFF.md)

## 从源码构建

准备 Windows MSVC Build Tools，在仓库目录执行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-cl.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-tests-cl.ps1 -SkipProductionBuild
```

仅在同轮生产构建成功且源码未变时跳过再次生产构建。CI 的 Python 是测试/打包
工具，不是产品必需服务。运行已验证的开发包不要求本机安装编译器。

## 历史交付与路线

历史报告和失败证据保留，不回写为新版本通过：
[N46D 队列修复](docs/nodes/N46D-QUEUE-HARD-AUDIT.md)、
[N46C 精确检索](docs/nodes/N46C-HARD-AUDIT.md)、
[N46B HTTP 边界](docs/nodes/N46B-HARD-AUDIT.md)、
[N44/N45 早期记录](docs/integration/DEVELOPMENT-STATUS.md)。
[Issue #2](https://github.com/youq616/qbrain/issues/2) 保持开放。
旧 `memory-preview-5ee79dfd` 和 `local-acceptance-n46e-v1` 不包含 N46F 修复。

## 许可

MIT；保留 [LICENSE](LICENSE) 和 [第三方许可说明](THIRD-PARTY-NOTICES.md)。
默认本地运行不表示开启外部模型后资料仍不外发。评审按所有者授权为工程自审，
不冒称第三方独立审核。
