# N47G：批量归档／恢复与只读预检

这是本地事实召回范围的显式管理，不是删除、自动遗忘或语义合并。最多一次选择
32 个同来源事实：先预检，再明确执行。任何一项的版本、状态或证据不合格，整批
拒绝；数据库在写入中报错，已做的本批策略和 revision 变更一并回滚。

## 输入

`fact batch-preview` 与 `fact batch-apply` 都从 UTF-8 JSON 标准输入读取：

```json
{
  "operation": "archive",
  "items": [
    {"fact_id": "<64位真实事实ID>", "expected_revision": 3},
    {"fact_id": "<另一个64位真实事实ID>", "expected_revision": 7}
  ]
}
```

operation 只接受 `archive` 或 `restore`。items 长度 1..32；ID 不可重复，必须来自
同一个已授权 source。每项只允许 fact_id 和 expected_revision。revision 必须是
1..2147483646 的整数，不接受字符串、布尔、浮点或自动修正。原始 JSON 重复键
（包括 JSON 转义后同名的键）会被拒绝；没有 apply、force、忽略错误等输入选项。
原始 payload 上限 8192 字节，结果元数据上限 32768 字节，不会截成不完整批次。

## PowerShell 调用

先用 `fact lifecycle` 或 `fact read` 取得现有 ID 和 revision；不要把示例占位符
当作真实 ID。使用同包 `scripts/Invoke-QbrainJson.ps1` 传输 UTF-8 JSON，避免
PowerShell 5.1 管道的系统默认编码损坏内容。它的具体参数以脚本内 help 为准。
也可由能够直接传输 UTF-8 stdin 的客户端执行以下参数：

```text
qbrain.exe fact batch-preview --brain my-brain --source my-project
qbrain.exe fact batch-apply   --brain my-brain --source my-project
```

两次输入使用相同 operation/items，执行恢复时换成 `restore` 并重新读取当前版本。
允许显式 `--stdin`，不接受 `--limit`、`--history`、`--query` 等其他读取参数。
不要把 PREVIEW 输出对象原封不动回传：输入仍只包含 operation 和 items，不能用
结果中的预测 revision_after 当作当前 expected_revision。

## MCP

仍使用原来的六个工具，不增加新工具名。预检：

```json
{
  "name": "memory_read",
  "arguments": {
    "source_id": "my-project",
    "view": "lifecycle_batch",
    "payload": "{\"operation\":\"archive\",\"items\":[{\"fact_id\":\"<真实ID>\",\"expected_revision\":3}]}"
  }
}
```

明确执行时使用 `memory_write`、`action: "fact_lifecycle_batch"` 和相同 payload。
正常来源限制和 `--allow-write` 等写授权仍必须满足。即使服务端允许写，memory_read
的预检路径也不能因 payload 中的字段变为执行；任何未知字段都会拒绝。
`view=lifecycle_batch` 不接受 query、limit、max_bytes、event_id、fact_id、predicate、
include_history、stale_after_days 等同级参数。普通记忆视图不接受新增 payload。
N47F 已声明的 `stale_after_days` 现在也正确通过 MCP 参数类型检查，仍只适用于
`view=lifecycle`，范围 1..36500，布尔值不算整数。

## 如何判断结果

预检结果 `result=PREVIEW`、`applied=false`：所有 revision_after/archived_after 只是
对本次读取快照的预测，不是锁定版本、预约或已经写入的证明。执行会重新校验，
其间有附加证据、撤回、遗忘、另一批归档等变更就可能导致拒绝。没有租约令牌。

执行成功是 `result=APPLIED`、`applied=true`；items 保持请求顺序，每项有 fact_id、
revision_before、revision_after、archived_before、archived_after 和 change。
counts.total 是请求项数，change 是本次需要改变的项数，unchanged 是已经处于目标
归档策略的项数。没有变化的项目仍校验版本及证据，但不重复递增 revision。
这些元数据不是原话、真实性评分或模型已经消费的证据。

## 一致性和资源边界

预检保持同一个 SQLite 读快照，不写库、不创建归档表、不生成备份、不接管调用方
事务。另一连接在读期间改变数据，本次可能看到完整旧快照；下一次调用会看到新
状态。执行拒绝外部未结束事务；在同一个写事务内重新校验全部项目后再写入。

每个校验阶段共用 512 次证据检查／8 MiB 原始会话处理预算；预检一个阶段，执行最多
两个阶段。超限整批拒绝，不跳过某个事实。事实必须保留有效完整原话证据、active
状态；被撤回、替代、过期、遗忘或损坏的事实不能借批量恢复复活。有效性依据该
阶段共同采样时间，不承诺证据以后不会过期。条目数和工作预算不是硬实时承诺。

首次归档仍沿用 N47F：先备份磁盘库并初始化可选归档表，然后执行策略事务。如果
在准备之后版本改变或执行失败，可能留下备份和空的可选表，但策略/revision 不会
部分提交。备份大小和 I/O 不受条目数限制。已有表无新迁移，单条 archive/restore
行为保持不变。

归档事实不再成为默认召回锚点，但仍作为其他事实的有效直接冲突证据出现；显式
read/conflicts 仍可查看。开启事实 Hook 时普通记忆旁路也不会撤销归档策略。关闭
事实 Hook 不等于删除旧普通记忆。旧二进制忽略归档表，降级可能重新召回。

## 验证和范围

同包 `verification/test_lifecycle_batch_process.py` 是隔离合成脑库的程序验收，
不是已登录 Claude/Codex 的模型验收。脚本依赖同包已有的
`verification/test_hook_fact_process.py`，不要只复制单个文件到其他目录。

```text
python -B verification/test_lifecycle_batch_process.py --binary qbrain.exe --report <新的报告路径.json>
```

这不会安装 Hook、连接模型、读取真实脑库或要求配置认证。代码级测试另覆盖中途
SQL 故障回滚、32/33 条边界、证据工作超限和真实双连接批次竞争。本阶段没有自动
选取陈旧事实、后台定时任务、使用计数、语义归并或自动可信度判断；N47F 的生命周期
年龄仍只是提示。没有以这些有限测试声称百万事件性能或全项目完成。
