# Qbrain 当前交付状态

## N47M：源码修复与限定范围验收完成

2026-09-18：`memory` / `context` 命名参数二次解析修复通过本阶段验收。
[PR #29](https://github.com/youq616/qbrain/pull/29)记录合并状态和最终提交身份。
**源码验收不等于发布新安装包；本次没有创建、覆盖或移动任何 Release / tag。**

查询文字、来源或脑库名称中的 `--brain`、`--source` 等只作为数据处理，
不会再次改写实际选项。来源名或脑库名 `--manual` 不再被当作手动采集授权。
真正的选项、原始证据、显式空值/缺省值语义、脑库选择优先级和写入许可保留。
生产代码只修改 `cmd_memory` / `cmd_context`，没有全 CLI 重写、schema 迁移、
新 MCP 工具、模型请求或默认采集开关变更。

## 固定源码与实际验证

| 身份 | 值 |
| --- | --- |
| 原始产品修复提交 | `c510e60ec935dcf756e7e29315908af060be999f` |
| 完整原生验收源码 | `15f6f3962984cb9a9d20c3b6a2790a9b768f119e` |
| 完整验收源树 | `571c24873615aa867fe037b0fb2f83975307371c` |
| N47M 固定 push 验证 | [35290029136](https://github.com/youq616/qbrain/actions/runs/35290029136) |
| N42 完整验证 | [35292424658](https://github.com/youq616/qbrain/actions/runs/35292424658) |
| N44 完整验证 | [35292424683](https://github.com/youq616/qbrain/actions/runs/35292424683) |

c510 到 15f 只增加接续计划和两个既有 CI 的分支触发条件；产品和测试源码相同。
最后的审核/状态归档提交不改变产品、测试、构建脚本或工作流，不能替代上述实际
构建身份。以 PR 的最终合并回执核对审核源树与合并源树。

| 验证 | 已执行结果 |
| --- | --- |
| N47M Windows 原生真实进程回归 | 60/60 检查，113 次命令；原有完整单元套件通过 |
| N42 / N44 完整原生与跨平台门槛 | 全部必需任务成功；两份 Windows 日志各核对 60 个注册组 |
| 原始 CI 工件回读 | 7 个工件、966 个源码文件、1,177 项核验通过 |
| 本轮原 N47M 回归与普通输入兼容 | 67/67，127 次命令；含 7 组退出码/stdout/stderr 字节对比 |
| 单独编写的工程自审探测 | 修复版 937/937，967 次命令；旧版 284 个重叠用例失败，证明能识别原缺陷 |
| 原有进程回归 | memory 44、context 65、fact 34、multiterm 112、MCP 边界 17、配置 6 全通过 |
| 本轮辅助工程验证 | 4/4 focused CTest；193 项报告验证器、10 项 MSVC 清单、32 项原生日志验证器测试通过 |

本轮附加探测和辅助测试在 Linux 执行，不冒充 Windows 运行。937 项包含 912 种
参数排列及额外边界，不是 937 个独立功能。284 项旧版失败也不是 284 个独立漏洞。
Windows 注册组含明确的 `SKIP-PG`；不能用组 PASS 宣称真实 PostgreSQL 已验收。

## 审核结论和边界

**结论：N47M 限定范围 PASS，未发现未解决的阻断项。** 审核由协调者本人另行进行
代码复核、重新编译、黑盒探测、旧版反向验证和工件回读。用户在 9 月 18 日明确
授权由本人审核；这不是另一个子代理、Claude Code 或第三方认证，也不保证绝对无缺陷。

详细证据、命令、失败记录、二进制区别和限制见
[最终自审](docs/nodes/N47M-FINAL-AUDIT.md)、
[证据索引](docs/nodes/n47m-evidence/FINAL-SUMMARY.json)和
[能力差异](docs/OPS-PARITY-DELTA-N47M.md)。
初始待验收记录保留，没有将当时的 pending 改写成历史 PASS。

## 当前公开下载仍为 N47L

[N47L Release：multiterm-preview-17e9a435](https://github.com/youq616/qbrain/releases/tag/multiterm-preview-17e9a435)
的 `qbrain-windows-x64-multiterm.zip` 为 2,114,341 字节，SHA-256
`ed44a43d79e1e76efa768e74872223cd5d867dfb92881fe67aab129789cd4408`。
**该旧下载包不包含 N47M 修复。** 它仍是未签名、非 latest 的开发预览；
原始发布状态完整保留于 [N47L 状态归档](CURRENT-STATUS-N47L.md)。

N47M 的 N44 测试工件已验证，但没有作为新公开 Release 发布：inner ZIP 为
2,115,638 字节，SHA-256 `9072c0ae4cae517cc6b759b17d1657fac7dd46265eece04461b757771f308ee3`；
其中 EXE SHA-256 `c455a082d4ee55c9ff61688919e39ba0b0a3a54f63a4de696285e5f7ecdb0faa`。
不要将它和 N47M 专项 native 报告里的另一次构建 EXE 混为相同二进制。

## 下一阶段

`search` 的选项前缀与字面查询语法仍需单独定义和修复，未包含在 N47M；原始复现
见 [历史记录](docs/nodes/n47l-evidence/NEXT-STAGE.md)。真实 PG、完整 ACL/DLP、
通用语义合并/冲突推断、使用确认与自动衰减、画像、模型质量/费用及正式签名
仍未完成。本阶段通过不等于整个项目完成。

当前不需要用户本机操作或本地 Agent；没有新增已登录客户端、模型消费或外发验收。
以后确需本机任务时，仍使用仓库文件加一个完整可复制提示词的交接方式。
