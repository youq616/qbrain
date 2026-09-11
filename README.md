# Qbrain

Windows 原生 C++20 / PowerShell Agent 记忆与知识库。默认 SQLite + FTS5，不要求 Docker、WSL 或 Python 服务。由 `Lordakee/qbrain` 的 MIT 代码继续开发；gbrain / OpenViking 是设计参考，不是完整功能等价声明。

## 当前交付：经过原生验证的记忆预览版

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

## 验证

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
