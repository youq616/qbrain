# N48Q：PostgreSQL 结构化事实、生命周期与使用回执

本模块接续 N48O 会话记忆和 N48P 分层上下文，把已有 FactStore 与显式使用回执 API 接入 PostgreSQL。SQLite 仍默认，不自动迁移现有数据库。结构化事实仍是有来源的完整用户陈述，不是模型自动推断出的真实结论。

## 首先理解安全边界

同一个 PostgreSQL DSN 下更换 `--brain` 名称不会创建独立租户；source 是应用逻辑来源，不是数据库行级安全。真实数据应使用分别授权的数据库和角色。不要把测试示例发到生产 DSN，不在聊天或仓库保存连接密码。此模块不包含 Hook 的 PostgreSQL 接入、自动置信度升级、自动解决矛盾、完整 DLP 或真实客户端消费认证。

首次合法写入会在已初始化的 UTF8/public 库中创建可选事实、生命周期或回执表。异常或不兼容的表、索引和清除组件会被拒绝，不通过覆盖未知数据库对象完成升级。服务器备份、TLS、角色配置由操作者负责；SQLite 文件备份工具不能备份 PG DSN。

## 已有接口的 PostgreSQL 能力

- 事实：create、attach、promote、read、recall、conflicts、retract、supersede。
- 生命周期：archive、restore、显式选择的批处理，以及只读候选分页。
- 使用回执：report-use、revoke-use、usage、usage-list、usage-batch-preview、usage-batch-apply。

以项目实际 CLI 帮助和已有 API 契约为准，不新增 MCP 工具名称。MCP 的来源允许清单和写默认拒绝保持。读取、创建事实或上报回执本身不调用外部模型；会话提取的外发许可仍是独立设置。

## 数据如何绑定

create 需要已经通过会话提取得到的 item_id 和 predicate，例如 tool.preference。返回 fact_id 和 revision。object 保留完整用户原话，confidence 仍为 null；truth_status 表示调用方陈述，不认证命题本身真假。助手和工具的陈述不自动成为用户事实。

attach 只能附加同一来源中、原话完全一致的独立证据；不是把不同说法强行合并。矛盾关系必须明确声明，不由新旧时间自动决定哪条是真。撤回和取代保留状态，重放旧 create 不会恢复已退休事实。归档只控制默认召回，仍可显式检查支持尚存的事实。

预期版本是乐观并发条件。attach、归档、恢复及支持变化可能推进 revision；调用方必须重新读取版本，而不是反复提交旧 expected_revision。每个原生线程需要自己的 Brain/Database 连接，不能让多个线程并发共享一个连接。

## 在已有授权环境中操作

下面展示的 JSON 应通过已有 UTF-8 桥脚本传给对应命令。fact_id、usage_id 均使用符合原契约的 64 位小写十六进制标识；item_id 必须来自目标库，不能使用另一来源的 ID。以下是结构示例，不是可直接操作生产数据的实际 ID。

创建事实（`fact create --source SOURCE --brain LABEL`）：

```json
{"predicate":"tool.preference","item_id":"<实际的 item_id>"}
```

读取当前版本：

```powershell
.\qbrain.exe fact read --source default --brain pg-demo --id $factId
.\qbrain.exe fact recall --source default --brain pg-demo --query 'Windows'
```

上报显式使用（`fact report-use`）：

```json
{"fact_id":"<实际 fact_id>","usage_id":"<为本次使用生成的 ID>","expected_revision":1}
```

撤销使用（`fact revoke-use`）：

```json
{"fact_id":"<实际 fact_id>","usage_id":"<同一个 usage_id>"}
```

Windows 5.1/7 的 JSON 输入请使用仓库 `scripts/Invoke-QbrainJson.ps1`，避免普通文本管道的编码转换。必须检查返回 ExitCode 和 JSON 错误字段；原始 PowerShell 示例未在用户电脑上执行。使用 PostgreSQL 的程序还需可信 libpq 依赖及匹配的 Visual C++ x64 运行库。未签名候选不能被称为签名稳定版。

## 回执不是模型消费证明

usage_id 在来源内去重。重复相同报告只保留一行，不把次数累加；撤销后的 ID 不能重新当作新使用。当前事实 revision 变化后，旧使用记录归入历史版本，不能仍计为当前版本使用。

回执只记录谁上报了哪个事实版本被使用，host_consumption_verified 保持 false。不能据此证明客户端真的把内容发给模型、模型正确采用了内容、质量提高或成本下降，也不会自动提高 confidence。

每事实最多 4096 条已保存回执，分页使用整个结果集的 snapshot。后续页必须携带上页游标和同一个 snapshot；中途版本或回执集合变化时，旧分页会被拒绝，应从第一页重新读取，不拼接两次状态。

## 批次和遗忘

usage-batch-preview 不写入。apply 需要相同选择与 snapshot，并重新核对所有目标的当前版本和完整回执状态。一个目标改变便整批拒绝，不能先写入未冲突的几行。成功后原 snapshot 不能作为可重复授权重新应用。

遗忘某个会话证据时，仍有独立支持的事实继续存在，但其版本变化；历史使用记录不被伪造成当前版本。最后一个支持被遗忘后，该事实的派生副本、证据关联、归档及回执被清除。不相关事实和其回执必须保留；重放已遗忘片段不能恢复它。

这里的清除不是磁盘安全擦除：原服务器 WAL、备份、外部日志和已导出的副本需要另行管理。

## 一致性与失败处理

PG 多查询读取使用模块所有的 REPEATABLE READ READ ONLY 快照。外部已开启或已失败的调用方事务会被拒绝，模块不代调用方提交。写入按固定顺序短暂锁定来源、页面、配置和依赖表，锁等待局部预算为 2500 ms。15 个有效表名必须解析到 public 的预期关系，同连接的同名临时表不能改变策略或数据来源。

fact_revision_conflict 表示需要重新读取事实版本；fact_usage_snapshot_conflict 表示不能继续旧分页；fact_usage_batch_snapshot_conflict 表示需要重新预览批次；fact_usage_withdrawn 表示该回执已撤销；fact_pg_schema_context 与 fact_*_schema_incomplete 表示连接或结构不符合本模块要求。不要用改版本号、关闭约束或扩大权限来隐藏这些错误。

以上是限定的模式识别，不是对恶意数据库所有者、任意 DDL 修改或所有业务语义的认证。高吞吐、全部PG模块、真实客户端/模型、签名稳定版和 Issue #40 仍需独立验收。

## 验证入口

原测试：`tests/test_pg_facts.cpp` 与 `.ci/test_pg_facts.py`。
实现后的补充黑盒审核：`.ci/review_pg_facts_closeout.py`，分别对 SQLite 和明确命名的一次性 PG 数据库执行；不要在生产数据库使用此测试。
原始资格流程：`.github/workflows/n48q-validation.yml`。
补充原生验证：`.github/workflows/n48q-outcome.yml`，保留源码/程序身份、原始请求和输出，缺少PG服务不能作为跳过通过。

实际接受结论、提交身份和运行编号见 `docs/nodes/N48Q-HARD-AUDIT.md` 与 PR #59；本说明不把未完成的工作流预先写成通过。
