# Qbrain

Windows 原生 C++20 / PowerShell Agent 记忆与知识库，默认 SQLite + FTS5。
不要求 Docker、WSL 或 Python 服务。由 Lordakee/qbrain 的 MIT 代码继续开发；
gbrain / OpenViking 是设计参考，不表示完整功能等价。

## 当前源码阶段：N47M

`memory` / `context` 参数二次解析修复已通过限定范围验收，见 [PR #29](https://github.com/youq616/qbrain/pull/29)、[当前状态](CURRENT-STATUS.md)与[最终工程自审](docs/nodes/N47M-FINAL-AUDIT.md)。查询或来源中的选项文字不再改写脑库、来源和实际参数；来源名或脑库名 `--manual` 不再授予采集权限。

完整 N42/N44 原生与跨平台验收、7 个工件的 1,177 项回读检查及单独编写的 937 项边界探测通过。审核人为协调者本人，属于用户授权的分离工程自审，不是独立子代理或第三方认证。**本次没有发布新 Windows Release；下面的 N47L 下载包不含 N47M 修复。**

## 已发布开发预览：N47L

**交付状态：已合并并发布，公开预览包已完成回读核验。** [N47L 预览 Release：multiterm-preview-17e9a435](https://github.com/youq616/qbrain/releases/tag/multiterm-preview-17e9a435) 的产品文件为 `qbrain-windows-x64-multiterm.zip`，大小 `2114341` 字节，SHA-256：

`ed44a43d79e1e76efa768e74872223cd5d867dfb92881fe67aab129789cd4408`

完整解压后阅读 `MULTI-TERM-RECALL.zh-CN.md`，并用同一 Release 的 `PROVENANCE.json`、`SHA256SUMS.txt` 和包内 `MANIFEST.json` 核对版本。产品使用原 CI 测试包字节，只更改下载名称，没有重新编译或重打包；这是**未签名、非 latest 的 prerelease**。运行预编译包不需要本机编译器。

实际产品与测试源码为 `17e9a435f94e45b3ca22d3da062ba4683c135c4b`，产品源树为 `f9d42819772df53dd8c6337c3cb19c8940d7023a`。[PR #28](https://github.com/youq616/qbrain/pull/28) 的合并、审核身份及发布核验记录见[当前交付状态](CURRENT-STATUS.md)；不要用旧 `dist` 或旧固定哈希入口识别这一版本。

[阶段审核](docs/nodes/N47L-HARD-AUDIT.md) · [测试与回读摘要](docs/nodes/n47l-evidence/SUMMARY.json) · [固定 CI 元数据](docs/nodes/n47l-evidence/CI-METADATA.json) · [发布回执](docs/nodes/n47l-evidence/RELEASE.json) · [恢复公开运行](https://github.com/youq616/qbrain/actions/runs/35234743634)

## N47L：选择连续字串、全部词或任意词

`fact recall` 支持三种明确的匹配模式，现有 MCP `memory_read(view=recall)` 使用同名 `match` 参数。

| 模式 | 含义 |
| --- | --- |
| 不传模式，或 `literal` | 将完整查询作为连续字串，保留输出格式；兼容探针验证字节一致，选项形状输入按下述缺陷修复 |
| `all_terms` | 同一个有效事实包含全部查询词 |
| `any_terms` | 同一个有效事实包含至少一个查询词 |

将 `my-brain`、`my-project` 换成实际脑库和来源。以下命令读取已经建立的事实：

```powershell
.\qbrain.exe fact recall --brain my-brain --source my-project --query "日志 前缀" --match all_terms --limit 5 --max-bytes 8192
.\qbrain.exe fact recall --brain my-brain --source my-project --query "Python C++" --match any_terms --limit 5 --max-bytes 8192
.\qbrain.exe fact recall --brain my-brain --source my-project --query "--match" --match literal --limit 5 --max-bytes 8192
```

只有明确选择 `all_terms` / `any_terms` 才分词。仅用 ASCII 空格、制表符、回车和换行分隔，最多 8 词，重复词也计数；完整查询最多 1024 UTF-8 字节。每个词仍按字串匹配，不自动中文分词、不推断同义词或真假，也不会把多个不同事实的词组合成一个结论。

查询词只筛选命中事实；它关联的有效直接反证即使不含查询词、或已被归档，也必须完整保留。证据和预算按整组处理，响应截断时的空结果不能证明没有匹配。`--match`、`--source`、`--brain` 等文字可作为 `fact` 查询内容，不会改变实际选项或脑库。

MCP 调用示例：

```json
{"name":"memory_read","arguments":{"source_id":"my-project","view":"recall","query":"日志 前缀","match":"all_terms","limit":5,"max_bytes":8192}}
```

该参数只适用于事实召回视图，不新增 MCP 工具或写权限，也不改变 Hook 自动取词 / 注入、安装默认开关、采集授权或数据库结构。[完整模式、字节边界和限制](docs/integration/MULTI-TERM-RECALL.zh-CN.md)。

本阶段固定原生证据来自 [N44 `35228307025`](https://github.com/youq616/qbrain/actions/runs/35228307025) 与 [N42 `35228306922`](https://github.com/youq616/qbrain/actions/runs/35228306922)，核对 60 个注册组和保留的 MSVC 门槛。N47L 专项规模为 16 场景 / 258 断言、真实 CLI / MCP 112 检查 / 126 命令；本地另已执行 193 项报告门槛与 32 项注册 / 构建清单检查。这些本地结果与 Windows 原生证据分开记录，最终原始工件回读数填写在[当前状态](CURRENT-STATUS.md)。

真实独立子代理发现并复验关闭了两个产品 P2：查询内容被二次当作选项，以及报告可用重复命令或自报退出码绕过覆盖检查。发布代码独立审核还关闭了一个资产 P2，现在上传后以固定 ID / size / digest 和下载字节核验同一组资产。审核为真实分别运行的工程子代理审查，不冒称第三方认证。

**N47L 下载包边界：其中的旧 `memory` / `context` 参数问题已在 N47M 源码修复，但本次没有替换该下载包。** `search` 的字面查询语法仍单独待办；[原始缺陷记录](docs/nodes/n47l-evidence/NEXT-STAGE.md)保留为历史证据。

当前无需本机补验或本地 Agent，没有新增 localhost、已登录客户端、PostgreSQL 或 provider-egress 验收。N47L 是限定范围的开发阶段，不代表整个项目完成。下面的 N47K 及更早能力继续保留。

## N47K：只读查看诊断，区分记录状态

```powershell
.\qbrain.exe hook diagnostics --config "C:\absolute\installed\config.json"
.\qbrain.exe hook diagnostics --config "C:\absolute\installed\config.json" --event UserPromptSubmit
```

示例路径需换成实际安装配置的绝对路径。只读该host的五个固定分事件文件，可按
事件或已有session-key筛选，不打开脑库、不触发Hook、不创建文件或锁、不调用模型，
也没有新增MCP本地文件读取入口。无效、缺失、不可读、过大、不安全或会话不匹配
的记录逐项标记，不回显无效内容或路径、不回退last-trace或临时文件。

`INSPECTED`/`present`是格式检查结果，不证明真实性、安装健康或模型消费；disabled
配置也可检查历史记录。配置64KiB、记录4096字节、最多五槽、完整JSON32KiB。各文件
独立观察，不是原子快照或抵御敌对目录竞争/硬链接的防御。
[完整格式、错误状态和限制](docs/integration/HOOK-DIAGNOSTIC-INSPECTION.zh-CN.md)。

两处MSVC链接清单遗漏已修复并加入默认源/对象检查。原生35186099196与35186099174
通过59注册组、诊断11场景107断言及60项CLI检查68预期退出，两Windows/portable/
Linux ASan/UBSan有对应证据。单独工程自审又重新GCC编译，执行诊断及旧Hook专项、
204报告测试、40命令160断言独立检查与318项原始工件回读。未发现本阶段未解决
P0/P1，不是绝对无缺陷、第三方/子代理或新增已登录客户端验收。

## 保留的 N47J：分事件诊断，不记录原始聊天

保留last-trace兼容文件，同时为两个固定宿主的五种事件分别保留最近一次已接受
处理记录。后续SessionEnd不会覆盖独立的UserPromptSubmit槽，最多十个事件文件，
每条不超过4096字节。只记录有限状态/阶段/计数/时间与session_key，不复制原话、
回答、上下文、异常消息、原始会话标识或凭据。

遗忘事件重放的诊断修复已包含：capture_status保留forgotten，不再留下上一次成功
记录；local为failed/extract，deferred可完成但不表示重新提取或记忆复活。
这是尽力写入的诊断，不是完整持久审计日志。锁忙、禁用、前置拒绝和I/O故障可能
不产生新记录；检查event/session_key/time，不能用文件存在或processed证明模型消费。
host_consumption_confirmed仍false，采集与事实权限、安装默认开关没有改变。
[完整诊断格式和范围](docs/integration/HOOK-DIAGNOSTIC-CHECKPOINTS.zh-CN.md)。

N47I的严格JSON输入保护保留：重复解码键、错误类型和不合法输入不能静默改写
写入含义。六工具名称与来源限制不变。以下为原有生命周期与记忆能力。

## N47H：分页发现候选，再明确决定如何整理

`fact candidates`与既有`memory_read(view=lifecycle_candidates)`只读发现当前来源
的维护候选：archive为有效active、未归档、最新有效支持达到年龄阈值的事实；
restore为有效active已归档事实。年龄不是使用频率、用户确认或可信度。
结果只返回metadata与N47G批量输入，不复制原话、不自动归档或恢复。

```powershell
.\qbrain.exe fact candidates --brain my-brain --source my-project --operation archive --stale-after-days 180 --limit 10 --max-bytes 8192
.\qbrain.exe fact candidates --brain my-brain --source my-project --operation restore --limit 10 --max-bytes 8192
```

每页最多检查100个原始候选、输出32项；按fact_id寻址，续查传上一页next_after_id
为after_id。预算中断不跳过未返回的当前事实。空页不等于扫描结束；has_more=true
可能仍有后续。progressed=false应提高预算或明确停止，不要无条件重复请求。
每页单快照，不是跨页原子全库快照；较小ID的新变化需重新扫描。cursor不代表权限。
[完整查询、分页和批量衔接说明](docs/integration/LIFECYCLE-CANDIDATES.zh-CN.md)。

## N47G：先预检，再原子化批量归档／恢复

`fact batch-preview`只读检查1..32个显式同来源事实；`fact batch-apply`明确执行。
候选响应的batch_payload对象可作为输入，每项只有fact_id和当前expected_revision。
预检不会锁定版本或写入，after预测不是许可；apply会在单事务内重验全部项目。
任何事实失效、版本变化或数据库提交失败都整批拒绝，不留下前半批成功。

```json
{"operation":"archive","items":[{"fact_id":"<真实64位事实ID>","expected_revision":3}]}
```

示例占位符不可直接执行；通过同包UTF-8脚本将真实JSON传入stdin。MCP沿用
`memory_read(view=lifecycle_batch,payload=...)`和
`memory_write(action=fact_lifecycle_batch,payload=...)`，payload为JSON字符串。
重复ID／JSON键、错类型和无关字段拒绝；读接口不能被apply／force参数提升为写入。
[批量调用和事务边界](docs/integration/BATCH-LIFECYCLE.zh-CN.md)。

## N47F：可撤销归档，不隐藏反证

原单条`fact archive`／`fact restore`保持。归档不修改原话、证据或退休状态，
仅限制默认事实召回／已开启事实Hook的命中入口；有效直接反证仍须保留，显式
read/conflicts仍可查看。归档不是遗忘、保密或安全擦除；旧二进制不认识归档策略。
恢复不能复活撤回、替代、过期、遗忘或损坏内容。

首次磁盘归档模块初始化先备份。准备和策略应用分开，应用失败可能留备份／空表，
但不会部分提交策略和版本。元数据不复制原话，最后证据删除后级联清理。
`fact lifecycle`／`memory_read(view=lifecycle)`的年龄来自最新有效支持created_at，
不是最后使用时间。异常时间unknown/null，未来时间clock_anomaly，不自动归档。
[单条生命周期与降级边界](docs/integration/FACT-LIFECYCLE.zh-CN.md)。

## 自动采集、整理与召回

N47E的`-EnableFactPromotion`独立默认关闭，要求`-EnableCapture`；N47D事实召回需要
独立`-EnableFactRecall`。明确开启后，本地规则提取的完整用户原话整理为证据绑定
事实，固定memory.<category>标签、confidence=null，不推断真假或语义冲突。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Install-QbrainMemory.ps1 -HostName Claude -ProjectPath "D:\Projects\MyProject" -Binary ".\qbrain.exe" -EnableCapture -EnableFactPromotion -EnableFactRecall
```

仅普通采集不传事实开关；仅召回可不采集。重装不传开关即关闭；卸载保留脑库和
备份，关闭不撤销旧事实。同原话独立支持可追加，重放不增版本；退休事实不自动
复活，新支持不清除归档。归档不绕过证据或批次限额。
[本地整理](docs/integration/LOCAL-FACT-PROMOTION.zh-CN.md) ·
[Hook响应预算](docs/integration/HOOK-FACT-RECALL.zh-CN.md)。

N47A证据生命周期、N47B成对冲突、N47C含直接反证召回保持。会话原文、来源隔离、
采集开关、去重、遗忘联动、项目Hook与可撤销安装、L0/L1摘录、独立许可摘要、L2分页、
缓存失效、六工具MCP、CJK子串、精确向量候选、Embedding标签隔离、批量队列与过期
结果拒绝保持。系统代理设置改变后须重启使用HTTP的进程。

## 通用验证边界和未完成项

全部旧事实、冲突、召回、promotion、Hook、生命周期、batch、candidate、严格JSON、
HTTP/队列/CJK及双PowerShell门槛在新产品CI中保留。真实PG DSN仍SKIP-PG，不能用
包围它的组PASS声称PG集成验收完成。Linux sanitizer不等于Windows内存检查。

用户转交N47E Claude自动链路通过摘要，与本轮程序测试分开；不用Claude结果替代
仍受认证阻塞的Codex。**Hook上下文交给已授权客户端，客户端可能发送给模型。**
没有新Qbrain请求不代表没有客户端外发。forget不是备份/WAL/旧上下文安全擦除；
哈希不是签名。数量和证据限额不保证SQL或备份I/O耗时，候选及预检可能过时。

通用语义合并／冲突推断、使用确认计数、自动衰减、画像、百万事件性能、PG对等、
完整ACL/DLP、模型质量费用和正式签名仍未完成。N47K完成不等于整个项目完成。

## 从源码构建与数据

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-cl.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-tests-cl.ps1 -SkipProductionBuild
```

源码构建需要MSVC；仅同轮生产构建成功且源码未变时跳过重复构建。运行预编译包
无需编译器；Python是测试工具依赖。升级前备份脑库，默认数据为
`%LOCALAPPDATA%\Qbrain\`。不上传真实密钥／个人聊天，不绕过客户端信任。
[安装卸载](docs/integration/QUICKSTART.zh-CN.md) · [接入说明](docs/integration/WINDOWS-MEMORY.md) ·
[本地Agent单提示词交接](LOCAL-AGENT-HANDOFF.md)。

历史报告和失败保留，[Issue #2](https://github.com/youq616/qbrain/issues/2)跟踪总路线。
MIT；保留[LICENSE](LICENSE)和[第三方说明](THIRD-PARTY-NOTICES.md)。
