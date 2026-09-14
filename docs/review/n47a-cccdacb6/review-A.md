# N47A 阶段独立审核报告 — 子代理 A（数据完整性与权限方向）

> 本文件为子代理 A 的原始审核意见，由父代理原样保留（未修改、未改判）。实际调用回执：ZCode Agent 工具，subagent_type=general-purpose，agentId=agent_cf35a611-1d5c-4b2d-924a-66a6fd5043a9（子代理自身无法看到会话 ID，其报告中如实写 unavailable；本 agentId 为客户端返回的真实调用标识）。审核对象：候选提交 cccdacb61e63c29f8b9eaba1c38fbeed3e23e54b / 源树 a15a91f7172622e2c8021403d84e63bf36f59147 / 基线 9ea592a041965ce5d4ca0d8720908d697b956157。

## 头部

- **verdict = PASS**（未发现未解决的 P0/P1 问题；仅有 P3 级观察项，见问题列表）
- reviewer: 独立审核子代理 A（代理类型 general-purpose；任务/会话 ID：unavailable，客户端未提供）
- 候选提交: `cccdacb61e63c29f8b9eaba1c38fbeed3e23e54b`（已验证 `git rev-parse HEAD` = 该值；源树 `git write-tree` = `a15a91f7172622e2c8021403d84e63bf36f59147`；`git status --porcelain` = 0 行，工作区干净）
- 阶段基线: `9ea592a041965ce5d4ca0d8720908d697b956157`；阶段提交链 e78ba23 → 12807f2 → 6bfc4a7 → cccdacb 均已核对
- 审核时间: 2026-09-13（环境日期）；只读审核，未修改 worktree、未读取任何密钥/真实脑库/真实聊天/全局配置

## 检查范围

**实际读过的文件（相对路径，均在只读 worktree）**：
- docs/nodes/N47A-PLAN.md、N47A-PLAN-AUDIT.md、N47A-STARTUP-REPAIR-PLAN.md（全文）
- docs/integration/EVIDENCE-FACTS.zh-CN.md（全文）
- include/qbrain/memory/fact_store.hpp、include/qbrain/storage/detail/startup_busy.hpp（全文）
- src/qbrain/memory/fact_store.cpp（全文，405 行）、src/qbrain/memory/session_memory.cpp（全文）
- src/qbrain/ops/memory_ops.cpp（全文）、src/qbrain/ops/registry.cpp（全文）、src/qbrain/ops/handlers.cpp（resolve_source/remote_source_allowed 段）
- src/qbrain/cli/commands.cpp（cmd_fact、cmd_memory、with_brain、bounded_stdin、opt/flag、帮助文本）
- src/qbrain/mcp/server.cpp（typed schema、args_from_params、handle_request tools/call 段）、src/qbrain/mcp/http_server.cpp（认证与写门控段）
- src/qbrain/storage/database.cpp（open/close/exec/backup_to/Statement 段）
- tests/test_n47a.cpp（全文 378 行）、tests/test_main.cpp（diff）
- .ci/test_fact_process.py、.ci/test_fact_unit.py、.ci/test_fact_report.py、.ci/validate_fact_report.py（全文）
- .ci/package_n44_development.py、.ci/test_validate_native_log.py、.github/workflows/n42-validation.yml、n44-validation.yml、CMakeLists.txt、scripts/build-cl.ps1、scripts/build-tests-cl.ps1（diff）
- tools/delivery/publish_fact_preview.py（全文）

**实际运行的命令及真实输出摘要**：
1. `git log --oneline -6 && git status --short && git diff --stat 9ea592a..cccdacb`（退出码 0）：确认提交链、干净工作区、25 文件 +1876/-31 差异。
2. `git diff 9ea592a..cccdacb -- <各文件>`（退出码 0）：逐文件核对实现/测试/CI/文档差异。
3. `git rev-parse HEAD` → `cccdacb61e63c29f8b9eaba1c38fbeed3e23e54b`；`git write-tree` → `a15a91f7172622e2c8021403d84e63bf36f59147`；`git status --porcelain | wc -l` → `0`（退出码 0）。
4. Python 3.13 + sqlite3 3.50.4（新建临时目录，未触碰 worktree/真实数据）——**SQLite 语义实测**，复制 fact_store.cpp 的精确触发器/外键结构：
   - 删除 1 条 memory_items（级联删 1 条 evidence）→ `[('f1', 2)]`（revision 由触发器 +1）；
   - 删除最后 1 条 item → facts 与 evidence 均为 `[]`（级联→触发器→物理删除事实）；
   - 以 `foreign_keys=OFF` 连接重复同样删除 → evidence/fact 孤儿行各剩 1（证明 FK=ON 检查是级联生效的必要条件，与代码 `FactStore::validate` 的 PRAGMA 检查互为印证）。
5. Python 提取 fact_store.cpp 源码中的原样 DDL（`R"SQL(...)SQL"`）执行（退出码 0 解析成功）；随后故意向关系表插入无父行外键 → `sqlite3.IntegrityError: FOREIGN KEY constraint failed`（脚本退出码 1，该失败即探针预期结果：复合外键 `(fact_id,source_id)→memory_facts` 确实强制执行）。
6. `grep -c 'scenario("' tests/test_n47a.cpp` → `15`；`56+2*(32-1)` → `118`，与 validate_fact_report.py 的 15 场景/118 命令门禁一致。

## 逐项核查结论（审核清单）

| 声明项 | 结论 | 依据 |
|---|---|---|
| 完整 user 原话绑定、quote 不可加工 | 成立 | `create` 只接受 predicate/item_id(/subject="user")（fact_store.cpp:276-279，`keys()` 白名单拒绝一切其他字段）；object 由 `evidence()` 从 DB 复制；`evidence()` 强制 `message.at("content")==quote` 且 `role=="user"`（:180-181）；上游 `validate_candidates` 同样强制整条消息相等（session_memory.cpp:248） |
| 否定保留在原话 | 成立 | 无任何子串→肯定转换；测试断言 `"不使用"` 保留在 object 中（test_n47a.cpp:65） |
| 置信度不可由客户端伪造 | 成立 | payload 白名单拒绝 `confidence` 键（fact_unexpected_argument）；输出固定 `confidence:null`、`untrusted_data:true`、`truth_status="caller_attested_user_statement"`（:200-201）；MCP/CLI 均无旁路 |
| 附加证据绑定 | 成立 | `attach` 强制 `e.quote == f["object"]`（fact_quote_mismatch，:302）；evidence 行钉住 quote_hash/payload_hash，读取时逐条重验（:210-211） |
| 到期（expiry） | 成立 | 三处一致（items.expires_at == events.expires_at == payload.expires_at）且 `expiry>now`（:161-162,177）；创建/附加/读取均用调用时 `at` |
| 篡改检测（tamper） | 成立且未夸大 | body sha256、page content_hash、event_id/item_id 派生哈希、存储 quote/payload hash 全部重验，篡改行被静默剔除、全失效则事实不可见（:210-217）；EVIDENCE-FACTS 明示"这不是签名：能改写整个数据库并重算所有哈希的攻击者不在此本地完整性模型的防护范围"（:103）——威胁模型边界诚实 |
| 软删/硬删语义 | 成立 | `p.deleted_at IS NULL`（软删，:161）与 `DELETE FROM pages`（硬删，测试 :167 的 mutations 列表覆盖两种）均使证据失效 |
| 最后证据遗忘级联 | **实测确认** | Python/sqlite3 3.50.4 实验证明 FK 级联会触发 `memory_fact_last_evidence`：剩余证据→revision+1；最后证据→事实及关系被物理删除；`memory::forget` 走 `DELETE FROM memory_items`（session_memory.cpp:442）即触发该链 |
| 替代不复活 | 成立 | 替代品证据丢失后旧事实保持 `superseded`（不复活）；同 quote/item 重复 create 返回旧状态回执（:284-285 `duplicate=true`，"Explicit retraction/supersession never resets"） |
| 多来源隔离与写权限 | 成立 | fact_id 含 source；全部查询 source 限定；evidence JOIN 强制 `e.source_id=?` 且 `p.source_id=e.source_id`；跨源 attach/contradict 分别得到 fact_evidence_unavailable / fact_not_found；写授权走既有 choke point：registry.cpp:86-94（remote 需认证 capability；MCP 需 --allow-write），CLI 本地信任路径与旧 memory 命令一致；MCP/HTTP 有 source allow-list（handlers.cpp:368-379）+ FactStore 二次 canonical/存在性校验 |
| revision 竞争 | 成立 | 所有写路径 `BEGIN IMMEDIATE` 序列化 + 事务内重读；retract/supersede 用客户端 `expected_revision`，`advance()` 以 `WHERE revision=?` + `db.changes()==1` 强制乐观并发（:231-238）；跨连接 retract 竞争测试断言恰好一方 fact_revision_conflict（test_n47a.cpp:284-289） |
| 初始化备份与错误回滚 | 成立 | 首次成功 create：先 evidence 预检→备份（`backup_to` 失败即抛出拒绝初始化）→事务内 DDL，失败整体 ROLLBACK（测试用 sqlite authorizer 注入 DDL 拒绝，断言 4 张表全不存在且旧数据存活，:220-229）；备份文件名含随机熵避免并发覆盖 |
| 读取不初始化/不写 | 成立 | `read()` 只调 `ready()`（sqlite_master/版本读取），未初始化时提前返回 `initialized:false`；测试断言 read 前后 `sqlite3_total_changes` 不变（:74-76） |
| 启动锁补丁范围 | 与批准范围一致 | 仅连接启动 3 条 PRAGMA 受 2500ms 单调时钟 deadline 的 busy handler 保护，成功即移除 handler、失败 `close()` 后重抛（database.cpp:56-65；StartupBusyWait 析构先于 catch 中 close，无悬空回调）；无整操作重试、无持久超时改动；测试覆盖临时/持久锁、WAL/FK 保持、连接复用（test_n47a.cpp:306-363） |
| 六工具名不变/发布禁用 | 成立 | 仅更新 memory_read/memory_write 描述与 schema；`publish-fact-preview` job `if: ${{ false }}` 禁用；发布脚本本身源绑定、fail-closed |

## 问题列表

**未发现 P0/P1 问题。** 以下为 P3 观察项（不阻塞）：

1. **[P3] fact_store.cpp:284-290 — 罕见路径下 create 触发裸 UNIQUE 冲突而非稳定错误码**。触发条件：`memory_facts` 已有同 id 行、但其**全部** evidence 行在 `load()` 重验中被剔除（如 quote_hash/payload_hash 被直改）而本次 create 的 item 证据恰好有效。[推断-静态] 该状态只能由绕过应用的直写 DB 造成（本身已超出声明的完整性模型）；实际结果：INSERT 撞 PRIMARY KEY → `std::runtime_error` → dispatch `catch(...)` → 通用 `memory_storage_error`。fail-closed、无复活、无信息泄露（sqlite 消息不外泄），但错误码不可诊断。建议：INSERT 前按 fact_id 存在性显式区分错误码。
2. **[P3] 逐事件遗忘语义的固有边界（文档已如实描述，非缺陷）**：同一句原话存在于两个 fragment 时，`forget` 一个 event 不影响另一副本及其支撑的事实；且从存活副本可 create 出**不同 fact_id** 的同 quote/predicate 新事实（id 含 item，fact_store.cpp:283）；两个同 object 事实因 `compatible()` 要求 `object != object` 无法互相 supersede/contradict（:254-258）。与旧 memory 模块逐事件遗忘语义一致（session_memory.cpp:439-452），隐私删除按 event 粒度成立。
3. **[P3] fact_store.cpp:81-90 — 备份放大**：`initialize()` 在事务前无条件生成新随机后缀全量备份；若 DDL 阶段反复失败（如锁、权限），每次重试都会新增一个 `.pre-facts-v1-*.bak`，无清理。需本地写权限才可触发，无正确性影响；建议失败路径清理本次备份或记录上限。
4. **[P3] 工具 schema 与实际限制不一致（收紧方向）**：memory_ops.cpp:87 的 memory_write JSON schema 宣称 `payload maxLength 262144`，fact_* 实际上限 16384（memory_ops.cpp:49）；CLI 帮助文本 `fact create|... [--stdin]`（commands.cpp:151）把 `--stdin` 写成可选，但写路径总是从 stdin 读取（`--stdin` 仅是被接受的空旗标，commands.cpp:429）。建议对齐文档。
5. **[P3] fact_store.cpp:395-397 — 预算截断后不中断扫描**：push→超预算→erase→置 truncated 后循环继续对剩余候选做证据验证（受 100 候选/512 次验证/8MiB 上限约束）。浪费有界，无正确性问题。
6. **[P3，阶段前已有设计] handlers.cpp:368-379**：`source_id=="default"` 对 MCP/HTTP 调用者免 allow-list（N20/N30 既有决策），default 源中的 facts 因此可被远程读取；写路径仍需 capability/--allow-write。非本阶段引入，提请知悉。
7. **[P3，流程] N47A-STARTUP-REPAIR-PLAN.md:44-47 要求"为真实独立代理添加明确 review handoff"**：worktree 内未见 N47A handoff 工件（docs/nodes 只有 PLAN/AUDIT/REPAIR-PLAN），若由 PR #14 描述承载则无法从本地验证。属流程项，由协调方确认。

## 威胁模型评估（哈希=篡改检测而非签名）

代码与文档一致且未夸大：PLAN（:34-36 "Direct DB mutation capable of recomputing every hash is outside this local integrity model; do not describe hashes as a signature"）、AUDIT（:14）、EVIDENCE-FACTS（:103）三处均明确整库写权限者可重算哈希。输出持续标注 `untrusted_data:true` / `caller_attested_user_statement`，`active` 状态被明确描述为版本状态而非证实（EVIDENCE-FACTS:12）。反例尝试（伪造 confidence、跨 source 读写、assistant/tool 角色提升、forged extracted 行、删除后同 quote 替代、过期后读取、并发 revision 交错、篡改 17 类 mutation）均在源码路径上被拒或被抑制，其中多数另有阶段测试断言（test_n47a.cpp、test_fact_process.py）；本人静态追踪结论与其一致。

## 未覆盖范围与未测试边界

- **无编译器（无 MSVC）**：未编译、未运行任何 C++ 测试；`tests/test_n47a.cpp`、CI 声明的 15 场景/380 断言、34 进程检查、118 命令均未复跑，不能视为已验证的运行结果。提交信息自述"new Windows results pending"。
- `FactStore::read` 依赖"外层 SELECT 保持活动使嵌套语句共享 SQLite 读快照"（fact_store.cpp:375 注释）——与 SQLite 文档化行为一致但属运行时语义，[推断-静态]，未实测。
- 并发场景仅静态推导（BEGIN IMMEDIATE 序列化、busy_timeout=2500 单次有界等待）+ 阶段测试代码审查；未做真实多进程压力复现。同连接多线程使用按文档明确不支持。
- PR #14 描述、远程 CI 运行记录、`evidence/` 产物不在只读 worktree 内，未核对。
- SQLite 语义实验（级联触发触发器、复合外键、FK=OFF 失效）在 3.50.4 上进行，代表本机 Python 附带版本，非产品捆绑 sqlite3.c 的精确版本。
- http_server 的请求体大小上限、认证细节等既有机制仅做了写门控路径抽查，未全面复审。

**结论：verdict = PASS**（针对本子代理负责的数据完整性与权限维度；上述 P3 项建议在后续节点处理，不构成合并阻塞）。
