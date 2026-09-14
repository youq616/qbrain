# Qbrain N47A 阶段独立审核报告 — 子代理 B（并发、测试与兼容）

> 本文件为子代理 B 的原始审核意见，由父代理原样保留（未修改、未改判）。实际调用回执：ZCode Agent 工具，subagent_type=general-purpose，agentId=agent_fb0d0024-f423-4f97-8820-7c303fd33899（子代理自身无法看到会话 ID，其报告中如实写 unavailable；本 agentId 为客户端返回的真实调用标识）。审核对象：候选提交 cccdacb61e63c29f8b9eaba1c38fbeed3e23e54b / 源树 a15a91f7172622e2c8021403d84e63bf36f59147 / 基线 9ea592a041965ce5d4ca0d8720908d697b956157。

## 头部

| 项 | 值 |
|---|---|
| **verdict** | **PASS**（无未解决 P0/P1；全部发现为 P3 观察项，附修复建议） |
| reviewer | general-purpose 子代理 B（独立审核上下文，与开发过程无关；任务/会话 ID：客户端未提供 → unavailable） |
| 候选提交 | `cccdacb61e63c29f8b9eaba1c38fbeed3e23e54b`（2026-09-14 07:07:25 +0800） |
| 源树 | `a15a91f7172622e2c8021403d84e63bf36f59147`（`git diff --quiet` 干净，HEAD 复核一致） |
| 阶段基线 | `9ea592a041965ce5d4ca0d8720908d697b956157` |
| 审核时间 | 2026-09-13（会话当前日期） |
| 审核 worktree | `C:/Users/Administrator/AppData/Local/Temp/2/QbrainN47A-Review-20260914-073332-17371/n47a-src`（只读，未做任何修改） |

## 检查范围

**实际读过的文件（相对路径，全文或关键段）：**
`include/qbrain/storage/detail/startup_busy.hpp`、`src/qbrain/storage/database.cpp`、`src/qbrain/memory/fact_store.cpp`、`include/qbrain/memory/fact_store.hpp`、`tests/test_n47a.cpp`、`tests/test_main.cpp`、`.ci/test_fact_process.py`、`.ci/test_fact_report.py`、`.ci/test_fact_unit.py`、`.ci/validate_fact_report.py`、`.ci/validate_cjk_report.py`、`.ci/test_validate_native_log.py`、`.ci/package_n44_development.py`、`tools/delivery/publish_fact_preview.py`、`.github/workflows/n44-validation.yml`、`.github/workflows/n42-validation.yml`、`CMakeLists.txt`、`scripts/build-cl.ps1`、`scripts/build-tests-cl.ps1`、`src/qbrain/cli/commands.cpp`、`src/qbrain/mcp/server.cpp`、`src/qbrain/ops/memory_ops.cpp`、`src/qbrain/memory/session_memory.cpp`（Tx 对比）、`docs/nodes/N47A-STARTUP-REPAIR-PLAN.md`、`docs/nodes/N47A-PLAN-AUDIT.md`、`docs/integration/EVIDENCE-FACTS.zh-CN.md`；回归排查还读了 `tests/test_n35.cpp`、`tests/test_n17.cpp`、`tests/test_n23.cpp`、`tests/test_embedding_queue.cpp` 的持锁段，以及 `include/qbrain/memory/session_memory.hpp`、`include/qbrain/core/brain.hpp`、`include/qbrain/util/utf8_display.hpp`（依赖符号存在性）。

**实际运行的命令与真实输出（隔离临时目录 `%TEMP%/n47a-subB-7f3a1`，已删除）：**

| 命令 | 结果 | 退出码 |
|---|---|---|
| `python test_fact_report.py`（.ci 副本） | `Ran 12 tests ... OK`（stderr 出现 `fatal: not a git repository` 属预期——副本无 .git，此时报告正确写 `source_commit: null, tracked_tree_clean: false`，反而实证了归因 fail-closed） | **0** |
| `python test_validate_native_log.py`（.ci 副本） | `Ran 11 tests ... OK`（含 49 组注册数断言与 n47a 不能复用 48 组日志的反例） | **0** |
| Python AST 调用点统计脚本 | 非嵌套调用点按运行时展开后 subprocess 总数 = **118**，与 `EXPECTED_COMMAND_COUNT = 56 + 2*(32-1) = 118` 完全一致 | 0 |
| `git diff --stat 9ea592a..cccdacb` | 25 文件，+1876/−31 | 0 |
| 场景名提取 `scenario\("(...)"` | **15** 个（grep 的 16 命中含第 29 行模板定义） | 0 |

## 逐项核查结论

### a. 有界启动锁等待（startup busy wait）回调生命周期 — 通过

- **无悬垂回调**：`StartupBusyWait` 是 `open()` try 块内栈对象（`src/qbrain/storage/database.cpp:56-65`）。异常展开时，try 块局部对象析构先于 catch 执行，即 `~StartupBusyWait()`（`startup_busy.hpp:32`，`sqlite3_busy_handler(db_,nullptr,nullptr)`）先于 `close()`，回调不可能在连接关闭后被调用；构造函数抛出（busy_handler 设置失败）也在 catch 内，`close()` 兜底。
- **无重入**：回调（`startup_busy.hpp:15-23`）仅调用 `sqlite3_sleep`（连接无关 API）与 `Clock::now()`，不触碰本连接其他 sqlite 句柄。
- **有界**：单一 steady_clock 截止时间 2500ms 覆盖三条 setup PRAGMA，单次睡眠 clamp 到 1–10ms，最坏溢出 ~10ms；超时返回 0 → `SQLITE_BUSY` → 抛出。
- **失败连接确定关闭**：catch(...) → `close()` → rethrow；`test_n47a.cpp:355` 断言 `!opened.is_open()`。
- **超时后可恢复重试**：`test_n47a.cpp:356-358` 在 ROLLBACK 后重新 `opened.open(file)` 成功，且 `PRAGMA busy_timeout==0`（启动等待不遗留持久 timeout，运行期恢复 fail-fast——与 `test_n35.cpp:38-39` 的旧契约一致）。
- 对比基线：补丁前 open() 内 PRAGMA 抛出时连接**保持打开**（泄漏句柄）；补丁后确定关闭，是严格改进。

### b. 并发测试真实性 — 通过（一处 P3 观察）

- **118 条命令**：以源码为准核实。`RACE_ROUNDS=32`，`EXPECTED_COMMAND_COUNT=118`（`.ci/test_fact_process.py:30-31`），AST 运行时展开计数=118（create 69、read_one 11、fact 11、rpc 11、memory 5、seed 5×2、process 1），精确相等且在 `validate_fact_report.py:26` 以 `==118` 强制（少一条即 FAIL）。
- **DELETE 模式持锁真实**：`test_n47a.cpp:313-322,343-349` 持有者执行 `PRAGMA journal_mode=DELETE; BEGIN EXCLUSIVE`，并用独立 prepared 语句读回 `PRAGMA journal_mode=="delete"` 自证夹具确实在回滚日志模式（EXCLUSIVE 才会阻塞读者）——非形式覆盖。第二阶段负向测试断言 `elapsed>=2000`（真正等满 ~2500ms 后失败），`elapsed<8000` 上界防挂死。
- **WAL 模式写者竞争真实**：`test_n47a.cpp:290-298` 用第二个连接持有 `BEGIN IMMEDIATE` 不提交，`create()` 的 Tx（busy_timeout=2500）阻塞后失败（elapsed<8000）、`busy_timeout` 恢复原值（123/456）、ROLLBACK 后重试恰好提交一次。
- **P3-2**：`.ci/test_fact_process.py:189-199` 的 32 轮双进程测试用 `threading.Barrier(2)` 对齐线程起点后各自 `subprocess.run`，子进程生成时间的抖动使两进程临界区**重叠是概率性的而非被断言的**；"一 create 一 duplicate" 不重叠时也成立，故该测试证明的是进程级幂等，而非确实发生了锁竞争。确定性竞争由上述 C++ 双测试覆盖，故仅降为 P3。

### c. 失败统计与验收门槛 — 通过

- **负向退出码不误报**：`record_result`（`test_fact_process.py:53-69`）先在锁内追加命令条目与 `unexpected_process_exit_N` FAIL 检查再抛出；主流程异常时若无任何 FAIL 检查则合成 `execution_interrupted` FAIL（`test_fact_process.py:223-224`），保证 `counts.fail>=1` 与 `result=FAIL` 一致——两条路径均有单测覆盖且我实跑通过。工作流侧：Linux 步骤显式 `set -euo pipefail`（`n44-validation.yml:35`），pwsh 步骤每条 Tee 后检查 `$LASTEXITCODE`（121-127 等处）。
- **空/部分报告不可绕过**：`validate_report` 依次强制 `result==PASS`、commit/binary/script sha 绑定、`tracked_tree_clean`、34 个命名检查集合与数量精确相等、counts 三元组一致、命令数 `==118` 且逐条 `exit_code==expected_exit`（expected ∈{0,1}）、出现 `error/error_type` 即拒——空报告在第一行就失败。`test_fact_report.py` 的 empty/missing/duplicate/fail/count/bool/error/命令历史反例我实跑全部通过。
- **`test_fact_unit.py` 的 `require_clean=False`**（P3-3 相关注）：允许本地脏树产出无归因（`source_commit=null`）的 PASS 单测报告，但打包门槛 `package_n44_development.py:71-75` 以 `source_commit=commit` 且默认 `require_clean=True` 复验，null≠commit 必拒。链条闭合。

### d. 阶段回归 — 通过

- **49 个测试组**：`tests/test_main.cpp` 数组实际数出 **49** 项（含新 `n47a_facts`，第 92 行）；`CMakeLists.txt`（qbrain_tests 源列表 + 独立 `qbrain_fact_tests` 目标）、`scripts/build-tests-cl.ps1:87`（源列表）与 `:149`（fact_store.obj）、`scripts/build-cl.ps1`（fact_store.cpp+obj）、`test_validate_native_log.py`（49 断言 + 新增 n47a 专属"不能复用 48 组日志"反例）、`package_n44_development.py`（`expected_count=49`，且 read_text 显式 utf-8 修复潜在编码问题）全部一致。15 个 fact scenario 名单与 `validate_unit_report` 的 `len==15`/顺序断言一致（正则实测 15）。
- **旧持锁测试不受影响**：`test_n17.cpp:1362/1373`、`test_n23.cpp:1189`、`test_n35.cpp:243-253` 的竞争者连接都在持锁**之前** open；启动 busy 等待只覆盖 open() 三条 PRAGMA，运行期 `busy_timeout` 仍为 0，"database is locked" fail-fast 契约保持。全库 grep 未发现"持锁期间二次 open 并期望立即失败"的旧测试（新 startup_lock_test 是唯一一个，且它期望等待）。
- **N46D/N46F**：`embedding_queue.cpp`、`hybrid`、`fts_search` 本阶段零改动；`session_memory.cpp` 仅被对照阅读未改。工作流保留 `qbrain_embedding_queue_tests`/`qbrain_cjk_tests` 全部门槛并新增 fact 门槛。
- **MCP 兼容**：`memory_read` 仅新增可选参数（view/fact_id/predicate/include_history），布尔改为字面量 `true/false` 仅影响新字段；`args_from_params(..., name=="memory_read")` + typed schema（Boolean/UnsignedInteger 严格校验）使 `include_history:"true"`、`limit:true` 等被拒（与 Python 端 `mcp_strict_inputs` 一致）。CLI `cmd_fact` 与既有 `cmd_memory` 模式一致（stdin 无条件读取、`--stdin` 为形式旗标——与 capture 行为一致，非回归）。

### e. 未审核前自动发布确已关闭 — 属实

- `.github/workflows/n44-validation.yml:228`：`publish-fact-preview` 作业 `if: ${{ false }}`（字面量 false，任何分支/事件都不会触发），带注释说明需独立子代理审核后方可发布。全仓 grep 确认 `publish_fact_preview.py` 仅被该禁用作业引用；`publish-cjk-preview` 的 `if` 限定 n46f 分支，本阶段分支不会触发。CI 仍产出候选 artifact（`upload-artifact if: success()`）。

## 问题列表

| # | 严重程度 | 位置 | 触发条件 | 预期 vs 实际 | 证据 | 修复建议 |
|---|---|---|---|---|---|---|
| 1 | P3 | `tools/delivery/publish_fact_preview.py:59-68` | 发布时对包内 `verification/fact-unit.json` 只做清单哈希固定，未调用 `validate_unit_report` 复验内容 | 发布前复验全部事实证据 vs 仅复验 fact-process（unit 靠 `validation.json` 摘要 + 哈希链间接保证） | 代码：`validate_facts(facts,...)` 之后无 unit 复验；缓解：作业已被 `if: ${{ false }}` 禁用且打包期已验证 | 启用发布前在 `verify_product` 中对 fact-unit.json 补一次 `validate_unit_report`（与打包期同样参数） |
| 2 | P3 | `.ci/test_fact_process.py:189-199` | 32 轮双进程竞争的子进程启动抖动 | 断言"确实发生锁竞争" vs 实际只断言幂等结果（重叠概率性） | Barrier 只同步线程起点；确定性竞争仅在 C++ 测试中 | 可选：记录一轮中 Tx 实际等待的证据（如耗时下界）或注明该测试为幂等性补充 |
| 3 | P3 | `.ci/test_fact_unit.py:25`、`.ci/validate_fact_report.py:54` | 单测报告的 `provider_calls:False` | "无 provider 调用"作为测量值 vs 实为静态字面量（从未观测） | `report={'result':'FAIL','native_windows':...,'provider_calls':False}` 初始化后无更新 | 改为从子进程行为/环境剥离推导，或在文档中明示这是声明而非测量 |
| 4 | P3 | `src/qbrain/memory/fact_store.cpp:280` | `create()` 的 Tx 前证据预读发生在无任何 busy 策略时，若此刻另一进程正做 DELETE 模式恢复/独占 | 有界等待 vs fail-fast 抛 "database is locked"（经 ops 层归为 `memory_storage_error`）[推断] | `create()` 第一步 `(void)evidence(...)` 在 `initialize`/`Tx` 之前；启动补丁只覆盖 open() 三条 PRAGMA | 可将预读纳入 2500ms busy_timeout 窗口，或接受 WAL 稳态下窗口极窄的现状 |
| 5 | P3 | `src/qbrain/memory/fact_store.cpp:50-63` vs `src/qbrain/memory/session_memory.cpp:56-67` | 维护性 | 共享 Tx 抽象 vs 两处近乎逐字重复（字段名 done/committed 不同） | 两段代码并排对比 | 提取到公共 detail 头（非本阶段必须） |
| 6 | P3 | `src/qbrain/cli/commands.cpp:404-435` | `qbrain fact create` 交互式运行未管道输入 | `--stdin` 旗标暗示可选 vs stdin 无条件读取至 EOF（阻塞） | `bounded_stdin()` 无条件调用；与 `memory capture` 现状一致 | 帮助文本注明"写操作从 stdin 读 JSON"（EVIDENCE-FACTS 文档已如此描述） |

**未发现 P0/P1/P2。**

## 未覆盖范围与未测试边界

1. **无编译器（无 MSVC/CMake）**：全部 C++ 结论为静态推导。`test_n47a.cpp`（含 `startup_lock_test` 的真实等待时长）、`StartupBusyWait` 运行时行为、`FactStore` SQL 语义、`qbrain_fact_tests` 可链接性（链接 `qbrain_mcp/qbrain_ops/...`，符号均已核实存在但未链接验证）、独立报告 JSON 实际格式、`checks>=380` 的精确断言数（静态调用点 69 check + 33 denied + 21 scalar，叠加 mutations×18、roles×4、caps 16/33 等循环倍增后数量级相符，[推断]）——均未在原生环境执行。
2. **`test_fact_process.py` / `test_fact_unit.py` 端到端未运行**（需已构建二进制）；118 命令数为 AST 静态核对而非运行记录。
3. **CI 与 PR #14 未访问**：workflows 逻辑为静态审阅，未观察真实运行日志；阶段文档所述"native run 34772721497 失败"无法独立复核。
4. **SQLite busy-handler 对 `PRAGMA journal_mode=WAL` 的调用路径**：基于文档复现证据（补丁前该 PRAGMA 在争用下报 "database is locked"）反推回调会被调用，[推断]；未用原生执行验证。
5. 遵守铁律：未读取真实脑库（%LOCALAPPDATA%\Qbrain）、密钥、全局配置；worktree 零修改；自建临时目录已删除。
