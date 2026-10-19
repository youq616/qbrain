# Qbrain 最新状态、完整蓝图与单次交接

核验：2026-10-19 UTC。此次发布保存工程上下文，不声明 N49D 完成。
[当前状态](../../CURRENT-STATUS.md) · [核验快照](SNAPSHOT-20261019.json) ·
[本地候选处置](LOCAL-CANDIDATE-INVENTORY-20261019.json) · [文档审查](DOCS-REVIEW-20261019.md)。

## 固定来源

- 仓库：https://github.com/youq616/qbrain
- 代码候选：[PR69](https://github.com/youq616/qbrain/pull/69)
- commit：[0900b19bb31f5c204771c6dd69decbf1337f4c98](https://github.com/youq616/qbrain/commit/0900b19bb31f5c204771c6dd69decbf1337f4c98)
- tree：`66b3838cf1ea71efa6a149abc225c138859c0414`
- parent：`2cb355812df2af5c77106056152d3d93e86784b9`
- 源码浏览：https://github.com/youq616/qbrain/tree/0900b19bb31f5c204771c6dd69decbf1337f4c98

Git 按冻结工作流 depth=24 有限获取固定 commit + detached checkout 是此处指定的取源码路径；不使用聊天附件、
未知 ZIP、旧工作副本或只下载单文件来拼接候选。tree/parent/Git blob 校验共同约束身份。
本次文档分支不作为受测源码；后续文档提交也不改变上列固定身份。

## 蓝图、构建与状态索引

所有链接均指向本仓库已存在资料；其历史结论只属于各自原候选。

- 治理与交接：[AGENTS](../../AGENTS.md)、[node process](../nodes/README.md)、[handoff convention](../../LOCAL-AGENT-HANDOFF.md)
- 总体分析与开发：[01 analysis](../01-ANALYSIS.md)、[02 development](../02-DEVELOPMENT.md)、[03 Windows build](../03-BUILD-WINDOWS.md)
- MCP：[04 requirements](../04-MCP-REQUIREMENTS.md)、[05 plan](../05-MCP-PLAN.md)、[06 usage](../06-MCP-USAGE.md)、[07 setup](../07-AGENT-SETUP.md)
- 总蓝图与全部既有范围：[08 master plan](../08-MASTER-PLAN-GBRAIN-PARITY.md)、[ops ledger](../OPS-PARITY-LEDGER.md)、[completion roadmap](../COMPLETION-ROADMAP.md)、[10 storage contract](../10-STORAGE-CONTRACT.md)
- 历史完成叙述：[09 project completion](../09-PROJECT-COMPLETION.md)；不能代替当前节点或整个项目的最新验收
- 最近检索模块：[N48T](../nodes/N48T-PLAN.md)、[N48V](../nodes/N48V-PLAN.md)、[N48W](../nodes/N48W-PLAN.md)、[N48X](../nodes/N48X-PLAN.md)、[N48Y](../nodes/N48Y-PLAN.md)、[N48Z](../nodes/N48Z-PLAN.md)、[N49A](../nodes/N49A-PLAN.md)
- 统一检索/客户端继承基线：[N49C plan](../nodes/N49C-PLAN.md)、[plan review](../nodes/N49C-PLAN-AUDIT.md)、[frozen outcome notice](../nodes/N49C-HARD-AUDIT.md)、[candidate guide](../integration/CLIENT-RETRIEVAL-CANDIDATE.zh-CN.md)
- 当前节点：[N49D plan](../nodes/N49D-PLAN.md)、[plan review](../nodes/N49D-PLAN-AUDIT.md)、[pending outcome](../nodes/N49D-HARD-AUDIT.md)、[RESULT](../nodes/n49d-evidence/RESULT.json)、[source manifest](../nodes/n49d-evidence/SOURCE-MANIFEST.json)、[MCP directory usage](../integration/MCP-DIRECTORY-SEARCH.md)
- 执行入口：[workflow](../../.github/workflows/n49d-mcp-directory-search.yml)、[qualification runner](../../.ci/run_n49d_qualification.py)、[source guard](../../.ci/check_n49d_sources.py)、[source controls](../../.ci/test_n49d_source_contract.py)
- 日常验收边界：[model quality/cost](../integration/MODEL-QUALITY-COST.zh-CN.md)、[model execution cost](../integration/MODEL-EXECUTION-COST.zh-CN.md)、[historical local runbook](../integration/LOCAL-AGENT-RUNBOOK.zh-CN.md)

## 一个完整可复制任务

以下整段作为一次任务转交；不要拆成多次提示。执行本任务不自动授予发布、合并、费用、真实账号或数据权限。

```text
继续 youq616/qbrain 的 N49D 工程验证，只处理此仓库。首先读 AGENTS.md，尤其最新 owner overrides 和单次交接约定；保持 Windows 11 native / C++20 产品边界。

背景：main 当前为 e0a27f829d970c24ed8c566023ada0911c0042b3，PR69 是独立 draft 修复候选，base 不是 main。固定待验证代码 commit=0900b19bb31f5c204771c6dd69decbf1337f4c98，tree=66b3838cf1ea71efa6a149abc225c138859c0414，唯一 parent=2cb355812df2af5c77106056152d3d93e86784b9。N49D approved plan、plan audit、pending outcome、RESULT、source manifest 和执行文件均已在该固定提交。最新交接/蓝图索引来自本文件所在文档分支；不要拿文档分支代替受测代码。

来源与安全：只从 https://github.com/youq616/qbrain.git 获取源码。选择本次新建、此前不存在的空工作目录，保留所有已有工作树和用户数据。执行 git init qbrain-n49d-verify；cd qbrain-n49d-verify；git remote add origin https://github.com/youq616/qbrain.git；git fetch --no-tags --depth=24 origin 0900b19bb31f5c204771c6dd69decbf1337f4c98；git checkout --detach 0900b19bb31f5c204771c6dd69decbf1337f4c98。获取范围与冻结工作流 fetch-depth:24 一致；保留 ancestry gate 所需对象，不复制完整历史/重复归档。如获取失败或所需 ancestry 对象不全，停止报告，不自行扩展为全历史。逐项执行 git rev-parse HEAD；git rev-parse "HEAD^{tree}"；git show -s --format=%P HEAD；git status --porcelain。前三项必须逐字等于上述固定值，最后必须为空。再执行 git rev-parse "HEAD:.ci/test_n49d_source_contract.py"，必须为 9527a0bfaf837aabdd492872024869f87e2317be。任一不符即停止，不能 reset、强推、改固定值或套旧补丁来凑通过。测试文件规范 Git 字节的 SHA256 为 82efc79a278f9cb8590469f4fda80b3420ad4cdf73468b4c23115dc7ead1804f；Windows 工作树可能换行转换，若校验 SHA256，须从 Git blob 二进制取字节，不能经 PowerShell 文本管道转码后比对。

读完 docs/nodes/N49D-PLAN.md、N49D-PLAN-AUDIT.md、N49D-HARD-AUDIT.md、docs/nodes/n49d-evidence/RESULT.json、SOURCE-MANIFEST.json、docs/03-BUILD-WINDOWS.md 和 .github/workflows/n49d-mcp-directory-search.yml 后，先确认平台、Python、CMake、编译器和 SDK 是否齐备。已有本地 1292 controls 是历史报告，不是你这次运行结果，更不是 Windows 原生验收。2026-10-19 精确 head 的全事件 Actions、check-runs 均为 0，PR reviews 为空。

尽量在具备工具链的远端工程环境完成 repo 工作。若允许启动 CI，先核对 workflow 在所选 ref 上可调度，再以 inputs.candidate 和 inputs.tree 精确传入上列值；不要默默改 candidate/ref 或把 pull_request 当作已配置触发器。当前 workflow 仅有指定 feature 分支 push 和 workflow_dispatch。若可调度入口缺失，报告准确阻塞，不改冻结源码以绕过。没有原生 Windows/合适环境时记录该门未运行；不在用户电脑安装大工具链，不用 WSL/Docker/Linux stub 冒充 Windows。

需要四个 job：linux-cmake、windows-cmake、windows-msvc、linux-sanitizers。每个 job 使用独立干净 checkout、源码目录之外且此前不存在的 build/output/package 目录，并使用真实平台执行。工作流会调用统一入口：python .ci/run_n49d_qualification.py run --source <此候选完整绝对路径> --build <新建外部构建路径> --output <新建外部证据路径> --package <新建外部打包路径> --commit 0900b19bb31f5c204771c6dd69decbf1337f4c98 --tree 66b3838cf1ea71efa6a149abc225c138859c0414 --job <四种 job 之一> --run-id <实际运行编号> --run-attempt <实际尝试编号>。CI 中必须使用实际 GitHub run/attempt；独立非 CI 环境若使用数字本地编号，单独声明其为本地运行，绝不可伪造 GitHub URL。无授权启动运行时，只报告就绪/缺失条件，等待具体执行许可。

按 approved plan 保留源码前后守卫、normal 与 python -O 控制、十二个 focused CTests、两条 Windows canonical sixty-group suite、direct-MSVC strict RunOnly、六类 process driver 的两种 Python 模式、实际 Windows HTTP/WinHTTP、ASan/UBSan、raw stdout/stderr、退出值、超时、阶段记录、候选/二进制/工件身份。不得替换为部分检查，不删失败记录，不提高预算或弱化断言来获得绿灯。四个 job 的 artifact 必须逐一下载回读，验证 manifest/archive SHA256、完整文件集合、源 tree 和原始输出；使用候选 runner 的 consume 子命令及真实 identity/摘要。产物缺失、过期、损坏、超限或不绑定该候选都只能是 incomplete/failed。

N49B/PR63、PR61 特有机制、PostgreSQL directory/cache/context/storage 工作和 N49D 计划列出的历史冻结探针均排除。不得获取、检查、重建、恢复或通过替代路径执行这些操作。保留默认拒绝写和 loopback token；仅用可丢弃合成 SQLite/本地 mocks，不读取用户脑库，不使用真实聊天、密钥或付费 provider。不要导入旧工作区脏树或 __pycache__。

完成原始证据核验后，交给真实独立非作者审查者，对照 approved plan 检查固定候选和工件；记录审查者身份、范围、命令、发现、限制。没有四 job 完整证据及独立 outcome review，不得把 N49D 标 done/PASS。本次文档审查也不是产品审查。代码若需修改，先给精确问题、计划约束和拟改文件，按授权及 node gate 开新候选，保留旧候选；原报告不继承到新 tree。

仅当后续确实需要用户本机/登录客户端验证且已有新候选预编译包时，才安排本机阶段：包必须事先位于仓库或版本化 Release，写明准确下载、SHA256、安全解包和命令，不要求聊天附件转运；没有新包就明确阻塞，不使用旧 N47X/N48K/N46E 包冒充新候选，也不把 Server CI 说成用户 Windows11。保存现有客户端配置、授权和未提交数据。

最终一次交付：固定 commit/tree/parent、所用环境与版本、逐 job 和逐必需门的通过/失败/未运行表、实际 run/attempt 与 artifact 链接及摘要、原始失败原因、独立审查结论与限制、未解决问题和下一步。不要只给计划，不虚报 native/客户端/模型/费用/PG/签名/Issue40 或全项目完成。不合并、不部署、不发行、不改变用户设置、不启用 auto-merge，不强推；需发布新的代码/工件时按当前授权执行，否则先明确请求。
```

## 恢复覆盖与明确缺口

此次可访问的三个 N49D 源码副本已按相对路径和 Git blob 与冻结候选对照：
timeout 副本 25/25 相同；另外两个副本各 24 个相同，唯一旧测试文件已被远端新版本覆盖。
这些副本并非完整用户电脑快照；没有宣称“所有电脑上的未提交内容都已找回”。
旧本地 commit `282d2c7…` 的 tree 等于已发布 v2 tree，不能当作新的未推送产品工作。
缓存、历史补丁和原始诊断 ZIP 保留在原位置，本次不重复上传、不认证其未核验内容。

本次没有取得用户电脑上的额外文件、最新 head 的四 job 原始工件、新 Windows 11 实测、
真实客户端/模型证据或新发行包；这些是显式未恢复/未完成项，而非上传遗漏后假称完成。
