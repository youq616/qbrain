# Qbrain

Windows 原生 C++20 / PowerShell Agent 记忆与知识库。默认 SQLite + FTS5，不要求 Docker、WSL 或 Python 服务。由 `Lordakee/qbrain` 的 MIT 代码继续开发；gbrain / OpenViking 是设计参考，不是完整功能等价声明。

## N46C：已验证的精确检索优化

测试源码 `728c2502ff66cedae218722458cac47f957236fc`；[PR #7](https://github.com/youq616/qbrain/pull/7) 与
[Windows 原生验证及开发包](https://github.com/youq616/qbrain/actions/runs/34661114802)。
在该运行的 Artifacts 选择 `qbrain-n44-windows-development-package`；名称沿用 N44，
以包内 MANIFEST 的源码 SHA 为准。CI Artifact 保留 14 天，不是永久 Release。

保留完整向量扫描与精确排序，同时把候选保留改为有界 Top-K；反向链接评分改为
来源隔离的批量计数，不读取链接正文。没有数据库迁移、新服务、缓存、ANN 或外发许可变更。
46 个原生注册回归组、51 项 HTTP 检查及原有记忆/MCP/Hook/两版 PowerShell 全部通过。

Windows 合成基准（2,000 页、16,000 片段、64 维、K=50）：候选保留由16,000条
片段记录变为最多50个页面；向量阶段7轮中位数 45.74→12.80ms；反向链接SQL
554→6次，结果与旧版完全一致。
这不是整个进程内存、实际模型召回正确率或Agent总延迟/费用的改善承诺。

开发ZIP SHA-256：`1f25ebbed82051f9f824485d92ea6b4a63871993b6a24cfe05780ad1feb9507b`。包未签名。
[逐项验收及失败诊断](docs/nodes/N46C-HARD-AUDIT.md) ·
[原始数值与交付清单](docs/nodes/n46c-evidence/RESULT.json)。真实Win11登录宿主、
PostgreSQL对等、语义质量与付费费用仍未完成。以下N46B和旧Release为历史交付记录。

## N46B 历史已验证代码：Windows 模型传输优化

测试源码 `2661e5205ba480c993210405d35c463efd8c6b6c`；
[PR #6](https://github.com/youq616/qbrain/pull/6) 和
[完整原生验证与开发包](https://github.com/youq616/qbrain/actions/runs/34626277700)。
在该运行的 Artifacts 中选择 `qbrain-n44-windows-development-package`；外层归档中
包含 `qbrain-windows-x64-development.zip` 和校验文件。Artifact 名称沿用 N44，但
来源与 MANIFEST 必须是上述 N46B 提交。CI Artifact 保留期为 14 天，不是永久 Release。

本轮修复整次网络请求截止时间、超大响应、半截结果、自动重定向和取消后的缓冲区
生命周期；45 个原生回归组、51 项原生网络检查，以及原有记忆/MCP/Hook/两版
PowerShell 验收全部通过。内层开发 ZIP SHA-256：
`750b5835ad4c924365ba052aef2ed2e7482e0033558cdf84bf15db6b724f160b`。

[本轮验收](docs/nodes/N46B-HARD-AUDIT.md) ·
[机器可读结果](docs/nodes/n46b-evidence/RESULT.json) ·
[升级兼容性](docs/integration/N46B-UPGRADE.zh-CN.md)。
开发包未签名；真实登录 Win11 Agent、付费模型质量/费用及 PostgreSQL 对等没有在
本轮完成。未改变采集、模型外发许可或数据库格式。

## 历史永久预览包：不包含 N46B 修复

**[下载 Windows x64 记忆预览版](https://github.com/youq616/qbrain/releases/tag/memory-preview-5ee79dfd)**。选择 `qbrain-windows-x64-memory-preview.zip`，完整解压后阅读中文说明。该包未签名，ZIP SHA-256 为 `fa106efa7066264c177c31f856d22828d750602ad953390088041d656d38296c`。原始 Windows 验证日志、校验值和来源信息同时发布。

- [PR #4：自动记忆接入、目录上下文、精简 MCP](https://github.com/youq616/qbrain/pull/4)
- [Windows 完整验证](https://github.com/youq616/qbrain/actions/runs/34616855167)
- [中文安装与卸载](docs/integration/QUICKSTART.zh-CN.md)
- [命令与行为边界](docs/integration/WINDOWS-MEMORY.md)
- [机器可读验证结果](docs/nodes/n44-evidence/RESULT.json)
- [剩余全盘优化路线](https://github.com/youq616/qbrain/issues/2)

测试对应源码 `5ee79dfd5ab2512f024fefc9054bd3da12d64f1f`。后续审核/文档修订不改变该次验证的二进制；预览包用 MANIFEST 和源码 SHA 标识，不凭旧的内部版本号判断新旧。

已实现：会话归档与有原文证据的记忆、自动采集开关、来源隔离、重试去重、遗忘防恢复；Claude/Codex 项目级 Hooks 和可撤销安装；L0/L1 摘录与可选模型摘要、L2 原文分页、缓存失效；六工具 MCP 模式与有限批处理。

**开发预览，不是“全盘优化已完成”。** 本批通过真实 Qbrain 进程的宿主事件重放，不是登录 Claude/Codex 后的模型回答质量验收。默认提取是保守规则，默认摘要是原文摘录。新记忆和上下文模块仅支持 SQLite。没有 Cursor 自动安装器、完整 gbrain 对等、ANN 或实际 token/费用节省保证。

## 使用与数据

从匹配的已验证开发包完整解压；执行其中的 PowerShell 安装器，不要使用历史 `dist/` 文件。安装默认只召回，`-EnableCapture` 明确开启该项目的本地采集。外发模型许可和 MCP 写权限不会自动开启。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Install-QbrainMemory.ps1 -HostName Claude -ProjectPath "D:\Projects\MyProject" -Binary ".\qbrain.exe" -EnableCapture
```

Codex 将 `-HostName Claude` 改为 `-HostName Codex`。客户端的项目/Hook 信任确认仍由用户审核，安装器不绕过。默认数据位于 `%LOCALAPPDATA%\Qbrain\`，不上传真实会话、数据库或密钥到仓库。试用已有脑库前备份；卸载保留记忆与备份。

## 早期记忆预览版验证（N44/N45/N46A）

Windows/MSVC 完整应用构建通过；44 个注册回归组全部报告通过，其中需要真实 PostgreSQL DSN 的用例明确跳过，不能计作 PG 验收。真实进程 memory 44、MCP 17、Hooks 69、context 65、项目本地配置 6 项通过。PowerShell 5.1/7 各安装 69、采集许可/路径 16、字节传输 8 项通过。GCC 可移植 CI 通过；另完成 C++ 记忆与上下文的 ASan/UBSan 检查。

完整日志、范围和失败修复见 [开发状态](docs/integration/DEVELOPMENT-STATUS.md) 与 [操作增量台账](docs/OPS-PARITY-DELTA-N44.md)。合成测试中的工具定义字节量由 30,224 降为 2,600；不代表实际 token 或账单下降相同比例。

## 从源码构建

在隔离的 Windows 开发环境，准备 MSVC Build Tools 后：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-cl.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-tests-cl.ps1 -SkipProductionBuild
```

仅在生产构建成功且源码未变时使用 `-SkipProductionBuild`。CI 的 Python 是测试/打包工具，不是产品依赖。历史 `dist/` 产物并非本批重建，不能代替本批包。

## 许可

MIT；保留 [LICENSE](LICENSE) 与 [第三方许可说明](THIRD-PARTY-NOTICES.md)。默认本地运行不代表开启外部模型之后资料仍完全不外发。
