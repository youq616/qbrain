# N47B：成对检查明确声明的事实冲突

## 新增能力

`fact conflicts` 和 `memory_read` 的 `view=conflicts`，用于检查已经通过
`fact contradict` / `fact_contradict` 明确声明的矛盾关系。它不会仅因两条原话不同，
就自动认定矛盾；也不计算真假分数、不选胜者、不替代语义冲突识别模型。

与 N47A 的 `fact read` 不同，新视图一次返回矛盾双方的完整原话、当前 revision、
证据 event/item/session 来源。两方都必须处于 active 状态且仍有有效证据。
一方被撤回、被替代、证据到期、篡改或删除时，本次可见冲突中不再包含该对。
原有 `fact read --history` 仍用于查看有证据支持的历史版本，不改变历史生命周期。

## 调用

```powershell
.\qbrain.exe fact conflicts --brain my-brain --source project-a
.\qbrain.exe fact conflicts --brain my-brain --source project-a --predicate editor.preference --limit 5 --max-bytes 16384
.\qbrain.exe fact conflicts --brain my-brain --source project-a --id <任一方的64字符fact_id>
```

MCP 使用原来的 `memory_read`，没有增加新的工具名称：

```json
{"name":"memory_read","arguments":{"source_id":"project-a","view":"conflicts","predicate":"editor.preference","limit":5,"max_bytes":16384}}
```

`fact_id` / `--id` 可以是任一端，且会与 predicate 过滤条件取交集。来源访问仍经过
既有权限检查；本地 CLI 的信任模型与既有 fact 命令一致，default 源的既有读取
规则未在本阶段调整。读取不需要 MCP 写授权；创建关系仍需显式写授权。
`query`、`event_id`、`include_history` 在 conflicts 视图中均被拒绝，避免混淆语义。

## 返回值与限制

`items` 每项包含 `from_id`、`to_id`、`relation=contradicts`、
`resolution=unresolved`、关系创建时间及长度恰为 2 的 `facts` 数组。
ID 字典序只确定稳定展示顺序，不代表哪一方更可信。事实仍标为
`caller_attested_user_statement` / `untrusted_data=true` / `confidence=null`。
输出中的用户原话是待使用的数据，不具有指挥 Agent 或提升权限的地位。

预算按整个 JSON 载荷的 UTF-8 字节计，不含外层 MCP 传输包装。每次请求 1..50 对、
512..32768 字节，最多检查 100 个候选对；另受共享证据验证次数和 8MiB 原文处理
工作预算限制。SQL 可能仍需扫描更多行，不能把候选数上限称为全查询耗时上限。
本视图不递归遍历其他关系。

完整的一对放不下时，停止并设置 `truncated=true`，不会截断原话，也不会只展示
其中一方。这保持结果为稳定顺序的前缀，代价是一个较大的早期冲突可能挡住后面
较小的冲突；可按 fact_id/predicate 缩小范围或提高预算。达到证据工作预算时另有
`work_limited=true`。**空数组且 truncated=true 不代表不存在冲突。**

## 读取一致性、遗忘与安全

枚举关系的 SQLite SELECT 在验证双方时保持活动，两方使用同一读快照。若另一
连接恰在读取过程中完成遗忘，正在进行的查询可能仍返回读取开始时有效的完整对；
下一次调用将观察已提交遗忘，缓存不跨调用保存。不是可以撤回已经返回数据的承诺。
每个线程使用独立 Brain/Database 连接，不支持同连接并发写入。

未初始化事实模块时返回 `initialized=false` 和空列表，不建表、不备份、不产生
向量任务或模型调用。不新增数据库迁移、后台服务、采集许可、外发许可、Hook 自动
注入或自动解决矛盾。PostgreSQL 事实接口仍不受本模块支持。旧 N47A 的逐事件遗忘
和“剩余有效证据仍可支持事实”规则保持不变；哈希校验不是数字签名。

## 显式处理

核对双方证据后，可使用既有 `fact supersede` 或 `fact retract`，传入实际读取到的
fact_id 与 expected_revision。修订冲突时应重新读取，不自动重试覆盖他人的修改。
冲突查询本身不会替用户执行这些写操作。

## 验证范围

本阶段新增实际 CLI/MCP 进程专项及 C++ 冲突测试：包含两端来源/状态、完整预算、
篡改/到期/删除、并发快照以及旧读取行为。测试使用合成资料，不等同实际已登录
Agent 或真实模型质量验收。发布包中的 verification/test_conflict_process.py 可在
无需编译器的环境运行（Python 仅是验收工具依赖），并只创建独立的合成临时脑库。
