# N47A：有证据的事实版本，而不是自动推断的事实

## 本轮能力

`fact` 命令和既有 `memory_read` / `memory_write` 工具增加显式的事实生命周期操作。
每条事实的 object 必须是已经提取的完整用户原话，由程序从证据复制；调用方只能指定
predicate 标注，不能另写 object、confidence 或把否定句截成肯定结论。例如原话
“我偏好不使用 MT5，而使用命令行。”会完整保存，不转换为 `uses_platform=MT5`。

输出的 subject 固定为 user，confidence 为 null，truth_status 为
caller_attested_user_statement，并标记 untrusted_data。消息角色和标注由调用方提供，
不是现实身份认证、语义真实性或可信概率。所谓 active 是当前版本状态，不代表事实已获证实。
本轮不会自动采集事实、推断矛盾、更新用户画像，或把事实注入普通 search / Hook 召回。

## 数据兼容与初始化

保留原有 `facts` 和其他表。普通启动、fact read、原有搜索不会初始化新表。
首次显式 fact create 在输入及现有证据通过预检查后，为磁盘脑库创建唯一的
`.pre-facts-v1-<随机摘要>.bak` 备份，再原子初始化以下独立模块：
`memory_fact_module`、`memory_facts`、`memory_fact_evidence`、`memory_fact_relations`。
旧 schema_version 不变。初始化后事实写入仍需事务内重新验证；写入失败不产生半条事实。
极端情况下初始化后证据失效，可能保留空的新模块，但不会产生无依据事实。

该模块当前仅 SQLite，要求 foreign_keys=ON；版本不符、缺表或缺关键触发器会拒绝。
备份失败则拒绝初始化。写锁只等待一次，最多配置 2500 ms，并恢复连接原 busy_timeout；
操作系统调度不是硬实时保证。不要在同一 Brain 连接上并发调用，线程使用各自连接。

回退到旧程序会忽略这些独立表，而不是自动删除它们。要物理删除模块或恢复备份需明确
维护操作。不要把“增量添加”理解为没有任何数据变更；升级已有脑库仍应先做好备份。
备份和 WAL 可能保留旧正文，遗忘不是磁盘安全擦除。

## CLI 使用

先通过现有 memory capture / extract 得到实际 `memory_items`，用 memory read
取得其 `item_id`。没有提取、不是 user 原话、跨来源、过期、被删或完整性不符的证据
不能创建事实。不要手工往数据库写伪造记录。

写操作从标准输入读取 JSON，并显式选择同一个 brain/source；例：

```text
qbrain fact create --brain demo --source project-a
stdin: {"predicate":"interface.preference","item_id":"<64位真实item_id>"}

qbrain fact read --brain demo --source project-a --id <fact_id>
qbrain fact read --brain demo --source project-a --predicate interface.preference --history

qbrain fact attach --brain demo --source project-a
stdin: {"fact_id":"<fact_id>","item_id":"<另一条相同完整原话的item_id>"}

qbrain fact contradict --brain demo --source project-a
stdin: {"fact_id":"<第一条fact_id>","other_id":"<第二条fact_id>"}

qbrain fact supersede --brain demo --source project-a
stdin: {"fact_id":"<旧fact_id>","replacement_id":"<新fact_id>","expected_revision":1}

qbrain fact retract --brain demo --source project-a
stdin: {"fact_id":"<fact_id>","expected_revision":2}
```

`expected_revision` 必须来自最新读取，不要照抄例子中的数字；追加/移除支持或关系等
操作可能已经增加版本。发生 revision_conflict 时重新读取，由调用方决定后续操作，
不自动覆盖重试。写入返回 fact_id、source_id、status、revision 等回执。

predicate 只允许 1..64 字节的小写 ASCII 名称（字母开头，随后字母、数字、点、短横线、
下划线）。同一原话证据与标注的重复创建会返回 duplicate，不把旧撤回或被替代记录复活。
相同完整原话可显式追加最多 16 条证据。不同原话不是“相同事实”的自动语义合并。

## 状态和关系

默认 read 只显示有有效证据的 active 版本；--history 包括仍有证据的 superseded 和
retracted 版本。创建两个不同值不会自动判为矛盾，也不会自动选择较新的为真。
`contradict` 只记录明确的、未解决的双向矛盾标注；不改变两个 active 值为已确认真相。
`supersede` 将旧 active 变为 superseded，并连接 active 替代版本。关系只能在同来源、
同 subject/predicate、不同完整原话且证据有效的事实之间建立，每条最多 32 个关系。
已替代/撤回对象不能作为新的 active 替代目标，不通过循环恢复历史状态。
替代事实后来遗忘，不会自动恢复旧事实。历史关系输出包含另一端的当前状态。

## MCP 使用与权限

不增加工具名；原六工具模式不变。读取用：

```json
{"name":"memory_read","arguments":{"source_id":"project-a","view":"facts","fact_id":"<fact_id>","include_history":true}}
```

写入用原 memory_write 的 action：fact_create、fact_attach、fact_retract、
fact_supersede、fact_contradict；payload 为对应 CLI JSON 对象的字符串。例如：

```json
{"name":"memory_write","arguments":{"source_id":"project-a","action":"fact_create","payload":"{\"predicate\":\"interface.preference\",\"item_id\":\"<item_id>\"}"}}
```

既有 source allowlist 与写默认拒绝仍然执行，--allow-write 及既有显式写策略不被绕过。
事实写入是一项明确操作，并不自动启用会话采集、Qbrain 模型外发或其他 MCP 写权限。
view=facts 不接受 query/event_id；旧 memory_read 不接受 fact_id/predicate/include_history。
未知字段、错误类型和超限输入明确拒绝，不忽略成另一个请求。

## 证据、遗忘与读取边界

每次创建和读取都会核对 item/event/page/source、完整原话、用户角色、原始消息索引、
归档与条目身份哈希、提取状态、过期时间和页面删除状态；证据附件另绑定当时的原话与
payload 摘要。被编辑、软删除、过期或篡改的证据不能继续支撑可读事实，没有原始归档回退。
这不是签名：能改写整个数据库并重算所有哈希的攻击者不在此本地完整性模型的防护范围。

原 memory forget 删除证据时，SQLite 外键和触发器清理新模块：还有其他相同原话支持则
保留并增加 revision；最后支持消失则删除事实及相关关系中保存的副本。旧程序的原有
forget 路径也可触发清理（必须保持 foreign_keys=ON）。不为了“保留历史”绕过遗忘。

每次最多考察 100 个事实候选、返回 1..50 条；max_bytes 为 512..32768。完整原话不会
为满足预算被切成另一句话；放不下则跳过并返回 truncated。单次最多做 512 次未缓存
证据验证、处理 8 MiB 归档正文；超过则标注 work_limited/truncated。缓存只在这次读取
内存在，不跨请求隐藏删除。结果上限与读取预算不等于整个 SQLite 查询的固定耗时。

## 验证与范围

包内 `verification/test_fact_process.py` 可对同包 qbrain.exe 执行隔离 CLI/MCP 测试，
使用合成脑库，不调用真实模型。不要求本机编译；Python 是验收工具而非产品运行服务。

```text
python -B verification/test_fact_process.py --binary qbrain.exe --report fact-process-local.json
```

实际验收来源由包内 MANIFEST 和验证报告确定。没有真实付费模型质量/费用、自动语义
冲突推断、衰减评分、跨源个人身份或 PostgreSQL 模块对等的通过声明。N47A 是可使用的
显式事实存储与生命周期基础，不是 N47 全部完成。
