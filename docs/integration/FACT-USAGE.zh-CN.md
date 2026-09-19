# N47T：明确上报和撤回事实使用记录

本功能位于 N47T 新源码，需要本阶段重新构建的 Qbrain。原 N47R 公开包没有这些
新命令；本阶段不替换现有 Release，不需要为继续仓库开发操作用户本机。

## 记录的是什么

`fact report-use` 仅记录：有写入权限的调用方声称使用了某个事实的某个版本。
它不证明模型真正看过或采用了记忆，不证明事实为真，也不是用户对该事实的确认。
因此所有结果明确返回 origin=caller_reported、host_consumption_verified=false、
fact_truth_verified=false、provider_calls=0。不存储本次回答、会话名称或原话正文。

普通 fact read/recall、search 和 Hook 输出都不会自动生成使用记录。这次不改变排序、
置信度、过期规则或自动衰减。已有事实的完整原话和支持证据仍由原 FactStore 校验，
新增模块不复制或改写它们。

## 三个命令和现有 MCP 路由

| CLI | 原有 MCP 工具内的路由 | 参数 |
| --- | --- | --- |
| fact report-use | memory_write，action=fact_report_use | JSON payload：fact_id、usage_id、expected_revision |
| fact revoke-use | memory_write，action=fact_revoke_use | JSON payload：fact_id、usage_id |
| fact usage --id ID | memory_read，view=usage | fact_id，及选定 source_id |

CLI 使用 --brain 选择脑库、--source 选择来源（缺省 default）。新操作没有新增 MCP
工具名，不绕过原来源权限。MCP 写操作仍默认拒绝，需要已有显式写权限；网络写入还
必须满足原有认证能力要求。usage 只接受事实 ID 和来源，不接受 history、query 或
limit 等不相关选项。其他命令的原始解析规则不变。

## 上报：先读取实际事实版本，保留同一次使用的回执 ID

先用新构建的 EXE 查看目标事实及 revision，不要把示例占位符当真实 ID：

```powershell
.\build\cl\qbrain.exe fact read --brain my-brain --source default --id '<实际64位fact_id>'
```

确实要上报该次使用时，在源码根目录用原有字节安全桥接脚本：

```powershell
$exe = (Resolve-Path '.\build\cl\qbrain.exe').Path
$brain = 'my-brain'
$source = 'default'
$factId = '<实际64位fact_id>'
$revision = 1 # 换成上一步实际读到的 revision
$usageId = [Guid]::NewGuid().ToString('N') + [Guid]::NewGuid().ToString('N')
$payload = @{ fact_id = $factId; usage_id = $usageId; expected_revision = $revision } | ConvertTo-Json -Compress
$r = & '.\scripts\Invoke-QbrainJson.ps1' -FilePath $exe -ArgumentList @('fact','report-use','--brain',$brain,'--source',$source) -InputJson $payload
if ($r.ExitCode -ne 0) { throw $r.Stdout }
$r.Stdout
```

两个 ID 都必须是 64 位小写十六进制。usage_id 是调用方生成并保留的不透明回执号，
不是把事实 ID 当作计数器。对同一次上报重试，应使用原来的同一个 usage_id；否则
会被当作另一次使用。重复成功返回 duplicate=true，并保留首次记录的 reported_at。
调用方不能提交自己的计数、时间、用户原话或其他任意字段。

上报要求事实当前有有效完整证据、状态 active、未归档，而且 revision 与提交值
一致。过期、已遗忘、已撤回、来源错误或版本过时会拒绝。同一来源的 usage_id 已
属于另一事实或另一版本时返回 fact_usage_id_conflict，不会转移旧记录。

即使原上报成功，事实随后变更或归档，再次 report-use 也会先执行当前资格检查，
可能返回版本/状态错误；幂等性不绕过新的事实有效性。其他来源可独立使用同名回执，
它们的读写仍分别受来源权限约束。

## 查询：当前版本和其他版本分开统计

```powershell
& $exe fact usage --brain $brain --source $source --id $factId
```

current_revision_use_count：未撤回且明确绑定当前事实 revision 的回执数。
other_revision_use_count：未撤回但属于较早 revision 的回执数，不算入当前版本。
withdrawn_count：已撤回回执数。stored_receipts 是上述三类总数，包含撤回墓碑。
last_current_revision_use_at 是当前版本最后一次未撤回上报的 UTC Unix 秒；没有则 null。

增加或遗忘一部分独立支持证据可能推进事实 revision，此前记录不会自动转到新版本。
归档事实可查询并标记 archived=true，但不能新增上报；归档不等于从记录中抹掉
过去使用。事实已退休或支持已过期时，usage 不返回无效事实的使用摘要。已有回执
仍可凭原 ID 撤回，不需要更改或复活事实。

这是有界的元数据摘要，不返回原话、逐条回执清单或历史会话。受原事实证据校验
工作预算限制，极复杂的事实证据无法在上限内完整读取时也会拒绝，不返回半截真相。

## 撤回：永久保留本回执的撤销状态

```powershell
$payload = @{ fact_id = $factId; usage_id = $usageId } | ConvertTo-Json -Compress
$r = & '.\scripts\Invoke-QbrainJson.ps1' -FilePath $exe -ArgumentList @('fact','revoke-use','--brain',$brain,'--source',$source) -InputJson $payload
if ($r.ExitCode -ne 0) { throw $r.Stdout }
$r.Stdout
```

重复撤回返回 duplicate=true，撤回时间不变。已撤回的 usage_id 不能通过重试上报
复活；这是保留墓碑的原因。撤回使用记录不会撤回事实本身，也不修改原话、支持或
事实 revision。事实版本改变、归档、退休或支持过期后仍允许撤回存在的回执。

每个事实最多保留 4096 条回执，包含已撤回记录。容量已满时，相同有效记录的重试
仍可识别为重复，但新 ID 返回 fact_usage_capacity；撤回不会释放墓碑容量。没有
静默驱逐、自动重用或全局无限去重承诺。这是每事实限额，不是全脑库磁盘配额。

## 首次写入、遗忘和降级边界

SQLite 的可选 memory_fact_usage_module / memory_fact_usage 在首次有效上报时
建立。新增记录的事务重新检查事实版本；并发重复用主键序列化。模块建立前沿用
数据库在线备份接口，在同目录生成 brain.db.pre-usage-v1-*.bak。只读查询、未知
回执撤回和前置不合格上报不会初始化该模块。

模块准备与记录写入是两个事务。若期间并发改变事实，可能留下已初始化的空模块
和备份，但不会写入失效回执。首次并发调用可能分别产生多个合法备份。数据读写
仍使用原 SQLite 外键设置；PostgreSQL 不在本功能支持范围。

遗忘最后一份支持后，原逻辑删除事实，外键连带删除该事实的全部使用与撤回记录。
仍有独立支持时保留事实与历史回执，同时依原逻辑调整 revision。自然过期只过滤
无效内容，不等于立即删除持久化数据。备份和 WAL 的安全擦除不由 forget 或本功能
保证，备份可能包含旧资料，应按用户自己的数据保留政策保管。

回退旧代码会留下不被旧程序使用的可选模块；不要手工删表或以降级绕过隐私/权限。
需要恢复完整旧状态时，先关闭所有进程并按备份恢复流程操作。当前实现不对恶意
本机管理员改库、外部客户端虚假上报或真实模型消费提供证明；它是后续使用分析的
可控记录基础，不是完成自动画像、语义确认或真实效果验收的声明。
