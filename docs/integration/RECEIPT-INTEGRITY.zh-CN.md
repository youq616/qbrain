# 使用回执完整性与完整 MCP 分页（N47Y）

本模块统一使用回执的上报、重复重试、撤回、汇总和逐条分页校验，并修复 MCP
入口不接受既有 receipt_state / snapshot 参数的问题。新源码才包含本次修复；
现有 N47X 公开包保持原样，本阶段没有替换下载或要求用户现在安装。

## 完整模块的操作范围

| 操作 | CLI | 现有 MCP 工具与参数 |
| --- | --- | --- |
| 明确上报与幂等重试 | fact report-use | memory_write，action=fact_report_use，JSON payload |
| 明确撤回 | fact revoke-use | memory_write，action=fact_revoke_use，JSON payload |
| 当前/历史/撤回数量 | fact usage --id ID | memory_read，view=usage，fact_id |
| 筛选与连续分页 | fact usage-list --id ID | memory_read，view=usage_receipts，fact_id、receipt_state、after_id、snapshot |

没有新增工具名称、数据库结构或权限。MCP 写入仍默认拒绝；读得到回执 ID 不代表
拥有撤回权限。正常数据的返回格式、ID、版本、首次上报时间和分页指纹不变。
回执仍为 caller_reported，不证明模型消费、用户确认或事实为真，不影响排名/衰减。

## 这次关闭的两个缺口

回执在异常导入或直接改库后可能以 BLOB 而非 TEXT 保存同一可见 ID。此前汇总可能
计入该记录、逐条页却拒绝，重试相同 ID 还可能添加另一行。测试只在合成脑库中主动
制造这类异常；不表示正常命令会生成它，也没有证据说用户资料已经损坏。

现在先校验实际存储类型、ID 字节长度/内容、重复身份、版本和时间，再计数、筛选
或写入。相同字节的 TEXT/BLOB 来源及事实别名、请求 ID 的来源内跨事实别名，会
明确拒绝而不是自动转型。写操作在既有事务锁内重新核验；不因重复请求绕过检查。
只校验选定逻辑身份的有界范围，不全库扫描其他来源，也不是任意数据库损坏审计。

此外，MCP 工具描述原本公布了 receipt_state 与 snapshot，但单独的参数入口拒绝
它们，导致健康数据的筛选和连续翻页也不能完成。现在这两个参数按字符串接纳；
错误类型、未知字段、错误筛选、缺少成对游标、失效快照和用于其他视图仍然拒绝。
这项修复经过实际持续运行的 MCP 进程测试，不仅是 CLI 测试或 tools/list 展示。

## MCP 分页示例

下面是 tools/call 的 params 对象。将占位符换成实际 ID；来源权限仍须满足原规则。

```json
{"name":"memory_read","arguments":{"source_id":"default","view":"usage_receipts","fact_id":"<实际64位fact_id>","receipt_state":"all","limit":25,"max_bytes":8192}}
```

成功首页若 has_more=true，下一次保留事实、来源和筛选，传回原 snapshot 与
next_after_id；下一页可以改变 limit/max_bytes。末页 has_more=false 时停止。

```json
{"name":"memory_read","arguments":{"source_id":"default","view":"usage_receipts","fact_id":"<同一fact_id>","receipt_state":"all","after_id":"<上页next_after_id>","snapshot":"<首页snapshot>","limit":25,"max_bytes":8192}}
```

若返回 fact_usage_snapshot_conflict，丢弃这轮已收集的部分页，重新从首页查询，
不能把新旧页混合。分页数量、字节预算、顺序及指纹语义沿用
[逐条审计说明](FACT-USAGE-AUDIT.zh-CN.md)。[上报与撤回说明](FACT-USAGE.zh-CN.md)
解释 expected_revision、幂等 ID、撤回墓碑和备份/遗忘边界。

## 损坏被拒绝后，不自动修复或盲目重试

fact_usage_invalid_metadata 或记录身份相关的 fact_invalid_id 表示该次读取/写入
无法信任所选记录。不要通过改 ID 重试、关闭校验、批量删除回执或 SQL 强制转型
绕过它。保留错误码及版本信息，停止相关写入，并在受控备份副本上确认异常来源；
完整恢复应按已核验的备份流程进行。错误本身不授权任何自动修复、删除或迁移。

拒绝路径会保留该操作开始前的应用行、schema 和备份；通用 CLI 打开脑库的既有
行为不在本次改写范围内。故意制造的 SQL ABORT 测试验证事务回滚，不等于物理
断电、磁盘损坏或所有并发顺序都已测试。合法但过期、归档或已退休事实的回执仍
可按原权限撤回；损坏的目标集合不能借撤回操作悄悄改变数据。

每事实 4096 条容量（包含撤回墓碑）、最后支持遗忘时级联删除、来源隔离均保持。
备份/WAL 安全擦除、敌意管理员替换索引/触发器、通用自动修复和 PostgreSQL 对等
不属于此模块。Issue40 的历史超时、真实客户端/模型效果和签名验收也未因此关闭。
