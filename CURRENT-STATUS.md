# Qbrain 当前交付状态

## 当前阶段：N47L 显式多词事实召回

**交付状态：已合并并发布，公开预览包已完成回读核验。** 本阶段为 Windows 原生开发预览，继续使用 C++20 / PowerShell 和 SQLite。运行预编译包不要求本机编译器、Docker、WSL 或 Python 服务。

N47L 为 `fact recall` 和现有 MCP `memory_read(view=recall)` 增加明确选择的多词查询：`all_terms` 要求同一个事实包含全部词，`any_terms` 要求同一个事实包含至少一个词。省略模式或明确使用 `literal`，仍按完整连续字串匹配并保留输出格式；兼容探针验证字节一致，选项形状输入按下述缺陷修复。有效的直接反证即使不含查询词、或已被归档，也必须完整返回。

| 版本身份 | 固定值或最终证据 |
| --- | --- |
| 实际产品与测试源码 | `17e9a435f94e45b3ca22d3da062ba4683c135c4b` |
| 产品源树 | `f9d42819772df53dd8c6337c3cb19c8940d7023a` |
| 审核提交 | `218482b5714a28cb8b27451310b8cafb6927076d` |
| 审核源树 | `babfb44341e5aec9576c3ccd84f88ac373871ebe` |
| [PR #28](https://github.com/youq616/qbrain/pull/28) 合并提交 | `17aba70b73374fc39a0bb220f038ba11018b4b4a` |
| [原始 N44 验证运行](https://github.com/youq616/qbrain/actions/runs/35228307025) | `35228307025` |
| [原始 N42 验证运行](https://github.com/youq616/qbrain/actions/runs/35228306922) | `35228306922` |
| 恢复公开运行 | [35234743634](https://github.com/youq616/qbrain/actions/runs/35234743634) |

发布核验以这组固定身份为准：产品提交至审核提交只能有 `docs/` 改动；合并源树必须与审核源树完全相同。文档审核提交不替代实际生成 EXE、测试报告和产品包的源码提交。

## 下载与使用

[N47L 预览 Release：multiterm-preview-17e9a435](https://github.com/youq616/qbrain/releases/tag/multiterm-preview-17e9a435) 的产品资产为 `qbrain-windows-x64-multiterm.zip`。完整解压后阅读 `MULTI-TERM-RECALL.zh-CN.md`；通过同一 Release 的 `PROVENANCE.json` 和 `SHA256SUMS.txt` 核对版本。

| 文件 | 大小与 SHA-256 |
| --- | --- |
| 产品 ZIP | `2114341` 字节；`ed44a43d79e1e76efa768e74872223cd5d867dfb92881fe67aab129789cd4408` |
| 包内 `qbrain.exe` | SHA-256：`0bf0a19edcc672b750790016ed0979e001529a46d91def8f7d8b9bdffd8aae69` |

产品 ZIP 使用原 CI 生成的 inner ZIP 字节，只更改下载资产名称，没有重新编译或重打包。它是 **未签名、非 latest 的 prerelease**，不是整个项目的最终发行；旧 Release 不覆盖，已有 tag 不移动。

将示例中的 `my-brain`、`my-project` 换成实际脑库和来源：

```powershell
.\qbrain.exe fact recall --brain my-brain --source my-project --query "日志 前缀" --match all_terms --limit 5 --max-bytes 8192
.\qbrain.exe fact recall --brain my-brain --source my-project --query "Python C++" --match any_terms --limit 5 --max-bytes 8192
.\qbrain.exe fact recall --brain my-brain --source my-project --query "--match" --match literal --limit 5 --max-bytes 8192
```

模式只影响本次事实召回。`--match`、`--source`、`--brain` 等文字可以作为查询内容，不能被二次解释为选项。该修复已覆盖 `fact` 参数读取及其脑库选择；下面列出的旧 `memory` / `context` 问题尚未修复。

只有明确选择 `all_terms` / `any_terms` 才按 ASCII 空格、制表符、回车和换行分词，最多 8 词，重复词也计数；完整原始查询最多 1024 UTF-8 字节。每个词仍按字串匹配，仅折叠 ASCII 大小写，不提供中文自动分词、同义词或语义推断。不会把不同事实中的词拼成一个新结论；预算不足会丢弃整组并标记截断，不能将截断后的空结果当作“没有匹配”。

## 验证与独立审核

**最终原生与交付证据结论：固定源码的两条 CI 全部必需任务成功；恢复运行 35234743634 成功，三个原资产与固定字节一致。** 原生结论必须来自上表两个固定运行和对应原始工件，不能沿用初始候选的 CI 结果。

| 验证范围 | 核对内容与规模 |
| --- | --- |
| Windows 原生与构建门槛 | N44 / N42 各自核对全部 60 个注册组；保留生产、全测试两条 MSVC 源文件 / 对象闭合检查 |
| N47L 专项 | 16 个场景、258 条断言；真实 CLI / MCP 112 项检查、126 次命令调用 |
| 其他平台 | 对应固定 N44 的 Server 2022 HTTP / 单元、portable 及 Linux ASan / UBSan 工件；Server 2022 不代表另跑完整 CLI / MCP 套件 |
| 已执行的本地工程检查 | 193 项报告验证器测试、32 项注册与 MSVC 清单检查通过；这些 Linux 检查与 Windows 实际运行分开记录 |
| 原始工件回读 | 7 份固定 artifact、完整源码树、原报告、包成员及 EXE 身份；最终实际回读数为 `1094` |

真实独立子代理分别审核存储、接口和报告门槛。初始候选虽通过原有 CI，仍在独立审核中发现两个产品 P2，现均已修复并复验关闭：

- `--match` 等查询文字被再次扫描为选项，可能改变模式、来源或脑库选择。`fact` 现在只读取严格解析后保存的参数值。
- 进程报告只核对数量和自报退出预期，重复命令也可能通过。现在固定语义命令顺序、完整 argv / stdin、跨命令动态 ID 和独立预期退出码；打包也包含新增验证依赖。

原有前 61 项检查的名称与顺序、81 次命令的 argv / 顺序 / 预期退出码保留，再追加 45 次回归调用；另对 29 组输入的 CLI / MCP default / explicit literal 做 116 次基线原始 stdout 字节比较。这不表示原 81 条命令的所有响应均做了字节比较。原缺陷 binary 会被新回归拒绝。独立报告复核还拒绝了原三种伪报告及 881 个篡改变体。这里的“独立”指真实分别运行的工程子代理，不冒称第三方认证。

发布流程的独立审核另发现并关闭一个资产 P2：下载比对后，同名同长度的新资产可能替换旧资产。现在首次 draft 即固定三个资产的唯一 ID、本地字节 SHA-256 和大小，在公开前后都核对相同 ID / digest；缺 digest 拒绝。公开前逐字节下载核对三个资产，公开后再次核对 tag、source、资产身份与非 latest 状态。

首发运行 [35233247840](https://github.com/youq616/qbrain/actions/runs/35233247840) 已重新通过 1094 项工件核验并上传三个草稿资产，随后因使用仅查询已发布版本的 by-tag 接口读取草稿而失败，未到公开步骤。恢复流程按固定草稿 ID `390787606` 和原资产 ID 下载复核，重新检查固定 CI、源码和包身份后公开同一草稿；没有重建 tag、Release 或替换资产。原 `PROVENANCE.json` 保留首发运行的原始字节，成功恢复的运行与提交另见[发布回执](docs/nodes/n47l-evidence/RELEASE.json)和[独立发布回读](docs/nodes/n47l-evidence/RELEASE-READBACK.json)。原失败记录保留在 [INITIAL-DELIVERY.json](docs/nodes/n47l-evidence/INITIAL-DELIVERY.json)。

[阶段审核](docs/nodes/N47L-HARD-AUDIT.md) · [测试与回读摘要](docs/nodes/n47l-evidence/SUMMARY.json) · [固定 CI 元数据](docs/nodes/n47l-evidence/CI-METADATA.json) · [完整用法](docs/integration/MULTI-TERM-RECALL.zh-CN.md)

## 下一阶段与当前边界

**最小下一阶段：修复旧 `memory` / `context` 命名参数的二次解析。** 同一最终候选上的隔离实测已确认：特定以 `--source` / `--brain` 为内容的参数组合，可能读取错误来源，或在失败前误建脑库目录；只调整真实选项顺序即可得到正常对照。这些处理器与基线相同，问题早于 N47L，当前仅已复现和登记，尚未修改生产代码。

下一节点将只修这两个处理器的已解析值读取和实际 brain 参数传递，补来源、脑库、原文 / 页面、默认优先级及不误建目录的回归，并重跑原生门槛。`search` 的前缀选项与字面查询存在另一个语法问题，单独定义边界后处理，不扩大成全 CLI 重写。详见[下一阶段范围与原始复现](docs/nodes/n47l-evidence/NEXT-STAGE.md)。

N47K 只读诊断、N47J 分事件记录、严格 JSON、分页候选、原子批量归档 / 恢复、明确开启的本地事实整理与 Hook 召回、证据生命周期、来源限制及双 PowerShell 安装路径保留。N47L 没有新增采集 / 外发授权、MCP 工具、数据库迁移、Hook 默认开关或模型请求。

真实 PostgreSQL DSN 仍为 `SKIP-PG`；没有新增已登录客户端、localhost、模型消费或 provider-egress 验收。未完成范围还包括通用语义合并 / 冲突推断、使用确认计数、自动衰减、画像、PG 对等、完整 ACL / DLP、模型质量 / 费用与正式签名。**本阶段的限定范围通过不等于整个项目完成。**

当前不需要用户在本机补做工作，也不需要本地 Agent。无需重复已经完成的客户端验收。以后只有确实必须本机执行的任务，才按项目规则给出一个完整可复制提示词，并先把所需文件放到仓库或版本化 Release，写清下载、完整性检查与用法。
