# N47H：只读发现待整理事实，按游标继续查看

这是维护候选查询，不是自动衰减或自动归档。仅在当前来源范围内检查有完整有效
证据的 active 事实；输出不复制原话，只包含 ID、当前 expected_revision、标签、
归档状态和证据创建年龄。原话可通过已有 fact read 明确读取。

## 查询

```powershell
.\qbrain.exe fact candidates --brain my-brain --source my-project --operation archive --stale-after-days 180 --limit 10 --max-bytes 8192
.\qbrain.exe fact candidates --brain my-brain --source my-project --operation restore --limit 10 --max-bytes 8192
```

archive：选择未归档且最新有效支持创建年龄达到阈值的事实。unknown 或未来时间
clock_anomaly 不当作陈旧；这不是最后使用、确认、可信度或真假评分。
restore：选择已归档且仍有有效证据的 active 事实，年龄不影响资格。撤回、替代、
过期、遗忘或损坏内容不会因此复活。不会创建事实表、归档表、备份或模型任务。

MCP 沿用 memory_read：

```json
{"source_id":"my-project","view":"lifecycle_candidates","operation":"archive","stale_after_days":180,"limit":10,"max_bytes":8192}
```

可选 predicate 是精确标签；after_id 是上一页返回的 next_after_id。该视图拒绝
query、fact_id、event_id、include_history、payload 等无关参数。其余旧视图也不
接受 operation、after_id，工具名称及默认写拒绝不变。

## 分页必须检查完整控制字段

按 fact_id 的二进制顺序向后查找，不使用 OFFSET。每次最多检查 100 个符合来源、
状态和归档策略的原始候选，再验证原话证据及年龄；返回 1..32 项以内。没有合格项
时 items 可以为空，batch_payload 为 null，不生成无效的空批次。

has_more=false 且 next_after_id=null 表示当前这一页的候选扫描结束。has_more=true
只说明尚有未检查的原始候选，不保证下一页有符合年龄条件的事实。

stop_reason 的值：end、result_limit、scan_limit、output_budget、evidence_budget。
scanned 只计完整检查过的行。游标推进到最后完整检查的事实，当前被预算中断的事实
不会被越过。空页也可能 progressed=true，需要用 next_after_id 继续。若
progressed=false 且游标与输入相同（首次可能为 ""），不要无条件重复循环；提高
max_bytes 后重试，或者明确停止并报告不完整。不能把空页写成“没有陈旧记忆”。

响应总预算 512..32768 个 UTF-8 JSON 字节，包含分页控制和 batch_payload。程序为
控制字段预留空间，所以不保证刚好塞满预算；连最小信封都放不下会报
invalid_read_budget。使用默认 8192 或提高至 32768。每页共享 512 次证据校验与
8MiB 原始转录校验预算；这些不是总 SQL 扫描或硬实时延迟保证。

每次调用使用一个 SQLite 读取快照，不持有跨页事务，也不签发授权令牌。after_id
只是边界，不要求这个事实仍存在。其他进程若插入或改变了已越过的较小 ID，须重新
从第一页扫描才能查看它；不能将跨多页结果说成某个时刻的原子全库快照。

## 和 N47G 显式批量执行衔接

有候选时，batch_payload 是一个仅含 operation 与 items 的对象，每项只有真实
fact_id 和 expected_revision，最多32项且不超过8192字节。它只是方便组装的输入，
不是许可或预先批准。核对候选并用同包 Invoke-QbrainJson.ps1 以 UTF-8 stdin 将
这个对象交给 fact batch-preview；明确决定后才交给 fact batch-apply。不要将整个
候选响应、预测 after 值或候选标签等额外字段传给批量写入。

候选查询与预检不锁定版本。新的独立支持、归档/恢复、撤回、遗忘等可以使旧选择
失效；apply 将重新核对证据和当前 revision，任何一项失败整批拒绝。不要自动更新
冲突的 expected_revision 以绕过失败。批量执行后继续翻页使用原 seek 边界；要刷新
较小 ID 的新情况需重新扫描。

归档不是隐私删除：直接反证仍按原规则可见，显式 read/conflicts 也能查看，旧程序
不认识归档策略。没有自动整理计划任务、使用计数、语义合并或新增 Hook 开关。
无需重做 N47E 登录客户端验收；本阶段的测试是隔离的程序和数据库实验。
