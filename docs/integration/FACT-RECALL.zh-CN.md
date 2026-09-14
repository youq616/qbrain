# N47C：按查询召回事实，并保留直接冲突证据

## 功能与入口

`fact recall` 与现有 MCP `memory_read` 的 `view=recall`，按完整查询字符串在有效、
active 的用户原话事实中匹配。返回完整原话与来源，不把“我不使用 MT5”改成“使用 MT5”。
它不是向量/语义搜索、分词或真假判定，不自动创建事实，也不改变旧 memories/facts/conflicts
视图。SQLite lower 的既有行为使 ASCII 大小写不敏感，不承诺全部 Unicode 大小写折叠。

```powershell
.\qbrain.exe fact recall --brain my-brain --source my-project --query "命令行" --predicate interface.preference --limit 5 --max-bytes 8192
```

MCP 调用仍只有原来的工具名，不增加权限：

```json
{"name":"memory_read","arguments":{"source_id":"my-project","view":"recall","query":"命令行","limit":5,"max_bytes":8192}}
```

query 必须非空、非纯空白，UTF-8 有效、不含 NUL、最多1024字节，并通过现有敏感内容检查。
中文连续子串可匹配；“命令 行”不等于“命令行”。百分号、下划线、引号都是字面字符，不是
通配符或 SQL。predicate 可选且精确匹配。recall 不接受 fact_id/event_id/include_history；
CLI 对应不接受 --id/--history，重复参数会被拒绝。limit 1..50，max_bytes 512..32768。

## 不只给出命中的一方

每个 items 元素是一组不能拆开的事实：match_fact_id 是命中的事实，facts 的第一项是它，
其余为所有仍有效的直接显式矛盾对方。每条 contradictions 记录说明 from_id/to_id 与关系。
即使对方原话完全没有查询词，也会一起返回，防止查询只呈现支持其中一方的证据。

conflict_state=recorded_conflict 仅说明记录了有效显式矛盾，没有选择胜者。
no_live_recorded_conflict 仅表示这份读快照中未找到有效的直接记录，不证明语义上没有矛盾。
所有事实仍携带 confidence=null、untrusted_data=true、完整 item/event/session 来源与 revision。

这是一层直接关系，不是递归图遍历：A-B-C 中只查询 A，不自动扩展 B-C。若 B 也匹配查询，
它会作为独立命中项返回自己的 B-C；不会因为 B 曾作为 A 的对方出现就丢掉它的其他证据。
因此不同命中项可能重复某些原话。输出中 neighbors_recursively_expanded=false 明确标识此范围。
不同原话本身不会推断产生冲突，必须已有 fact contradict 显式关系。

## 快照、有效性与截断

外层查询先按原话匹配和来源/predicate筛选，再检查最多100个候选，旧的相关事实不会仅因
最近写入了100条无关事实而遗漏。顺序为 created_at 降序、fact_id 升序，不是置信度或真值排名。
双方证据共享一个 SQLite 读快照和一次调用内的工作预算。另一连接在读取中提交遗忘时，当前
读取仍可能返回原快照的完整一组；下一次调用必须反映遗忘，没有跨调用证据缓存。

撤回/替代的命中项、未提取原话、到期/篡改/删除的证据不返回。无有效证据的对方不复制到结果。
最后证据遗忘的原有级联清理继续生效；失去替代事实不复活旧版本。

整次调用沿用512次证据验证、8MiB转录校验工作预算；每个事实最多32条直接关系。
单个命中组放不进 max_bytes，或者加载对方时耗尽工作预算，整组不输出，只设置 truncated。
预算包含 JSON 载荷本身，不含外层 MCP 协议封装。不截断原话或只给出方便的一方。

空 items 且 truncated=true 不表示没有匹配/冲突。可缩小 predicate 或查询范围、增大预算。
第一个过大的组会停止后续输出，保证稳定前缀而不是暗中优先较短证据。数量/工作上限不代表
数据库底层最多扫描100行，也不是硬实时延迟保证。

## 接入和数据边界

这轮是可供 Agent 主动调用的事实召回接口，没有自动打开 Hook 事实注入；自动宿主接入、
显式开关和总上下文预算属于下一阶段。既有 Hook 继续原有普通记忆召回行为。
读取不建表、不备份、不改 revision、不创建任务、不调用模型，不新增数据库迁移。
首次明确事实写入的 N47A 备份/初始化语义仍由原实现负责。FactStore 仍仅支持 SQLite。
哈希用于本地完整性检查，不是数字签名；能改写整库并重算哈希的攻击者不在该模型内。

## 免编译专项

交付包提供 verification/test_recall_process.py，只用 Python 标准库与同包 EXE：

```powershell
python -B .\verification\test_recall_process.py --binary .\qbrain.exe --report "$env:TEMP\qbrain-recall-result.json"
```

脚本创建一次性的合成数据根，执行真实 CLI/MCP，不使用正式脑库或付费模型。它不是已登录
真实客户端验收。独立拷贝中的 source_commit=null 是没有 Git 来源的正确标记，须另外核对
版本包 SHA256/PROVENANCE；不能假称当前目录的任意 HEAD 就是 EXE 来源。
