# Qbrain

Windows 原生 C++20 / PowerShell Agent 记忆与知识库，默认 SQLite + FTS5。
不要求 Docker、WSL 或 Python 服务。由 Lordakee/qbrain 的 MIT 代码继续开发；
gbrain / OpenViking 为设计参考，不表示完整功能等价。

## 当前源码阶段：N47N

`search` 支持明确的字面查询边界；查询中的 `--brain` 等文字不会再次变成
选项。无效参数在打开脑库前拒绝。N47M 的 memory/context 参数与采集授权修复
继续保留。本次只做源码验收，不创建或替换 Release/tag。

```powershell
.\qbrain.exe search --brain my-brain --no-vector --json --query "--brain sentinelneedle"
.\qbrain.exe search --brain my-brain --no-vector --json -- "--brain sentinelneedle"
```

将 `my-brain` 换成实际脑库。`--query` 保留一个参数的原文；分隔符后的参数作为
查询词连接。字面边界不改变后端分词或排名，也不是精确字串搜索模式。未知、重复、
缺值、混合形式、空查询和错误数字/模式会报错，不再沿用旧版的静默宽松解析。
[完整语法与兼容边界](docs/integration/SEARCH-ARGUMENTS.zh-CN.md)。

最终验收源码为 `c26ec5e512d9ba960b86c9ced5b9b4976b031f2c`。N47N、N42、N44
和清单预检均通过；Windows/Linux 搜索专项各为 361 项解析检查、226 项进程检查
（302 次调用）。之前的文档清单回归已恢复并重验，旧 a587/f2ba 收尾记录不再
作为最终依据。新增 356 种 C++/Python 字节读取对照未发现错误放行。
审核由协调者本人另行进行，不是独立子代理或第三方认证，也不保证项目绝对无缺陷。
[当前状态](CURRENT-STATUS.md) · [最终自审](docs/nodes/N47N-HARD-AUDIT.md) ·
[PR #31](https://github.com/youq616/qbrain/pull/31)。

## 已发布下载与源码不是同一版本

当前公开预览仍为 [N47L multiterm-preview-17e9a435](https://github.com/youq616/qbrain/releases/tag/multiterm-preview-17e9a435)。
**其中的 qbrain-windows-x64-multiterm.zip 不包含 N47M/N47N 修复。** 本次没有发布
新应用包。原包为未签名、非 latest 的 prerelease；不要用旧下载验证新源码语法。
下载身份、SHA-256 和历史发布证据见 [N47L 状态](CURRENT-STATUS-N47L.md)。

## 已有能力、构建与限制

已有事实与直接反证召回、原话证据生命周期、显式批量维护、项目 Hook、分层上下文、
只读诊断、可撤销安装、来源权限和默认关闭的采集/事实开关均保留。各能力的完整
示例、历史证据和限制保留于 [N47M README 归档](README-N47M.md)，内容未改写。
[快速接入](docs/integration/QUICKSTART.zh-CN.md) ·
[Windows 接入](docs/integration/WINDOWS-MEMORY.md) ·
[规范操作清单](docs/OPS-PARITY-LEDGER.md)。规范清单保留原表，不由归档链接替代。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-cl.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-tests-cl.ps1 -SkipProductionBuild
```

仅在同轮生产构建成功、源码未变时跳过重复构建。源码构建需要 MSVC；预编译应用
不需要编译器，Python 是测试依赖而非产品服务。升级前备份 `%LOCALAPPDATA%\Qbrain\`。
不要上传真实密钥或聊天。`--no-vector` 只关闭查询嵌入，不代表禁用所有 LLM 重排。
真实 PostgreSQL、完整 ACL/DLP、模型消费/外发、正式签名和完整项目完成均未由本阶段
验收；具体范围以审核记录为准。需本机工作时仍遵循 [单提示词交接](LOCAL-AGENT-HANDOFF.md)。

MIT；保留 [LICENSE](LICENSE) 和 [第三方说明](THIRD-PARTY-NOTICES.md)。
