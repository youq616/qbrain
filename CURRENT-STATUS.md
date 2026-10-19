# Qbrain 当前状态：2026-10-19 同步

本页核验时间：2026-10-19 09:02 UTC。此次为文档归档与交接，不是产品验收、合并或发行。
[完整交接与蓝图索引](docs/handoffs/LATEST-HANDOFF-20261019.zh-CN.md) ·
[路线增量](docs/COMPLETION-ROADMAP.md) ·
[机器可读核验](docs/handoffs/SNAPSHOT-20261019.json)。

## 1. 主分支、继承基线与当前候选分别是什么

- main 仍为 `e0a27f829d970c24ed8c566023ada0911c0042b3`，截至核验是 N48R / PR60 合并。
  [上一版 N48R 状态](CURRENT-STATUS-N48R.md)按原内容保存；其运行记录只属于原候选。
- N49D 计划采用的 N49C 基线为 `cfe1ef58e244b51092c2248804b663b6c28913d7`，
  tree `75b69ad389630e51528ddb5536a27255203470df`。这是计划记录的已接受基线，不能当作 main。
  N49C 的仓库内 pending 通知为发布前冻结记录；最终外部报告应绑定原候选，
  本次未重取该报告，不把继承能力重新认证为通过。
- 当前修复候选是 [PR69](https://github.com/youq616/qbrain/pull/69)，仍 open / draft，未合并。
  head 分支 `diagnostics/n49d-progress-gate-repair-5a387bda-v2-timeout`；
  base 分支 `diagnostics/n49d-progress-gate-repair-5a387bda-v2`，并非 main。
- 固定代码 commit：`0900b19bb31f5c204771c6dd69decbf1337f4c98`；
  tree：`66b3838cf1ea71efa6a149abc225c138859c0414`；
  唯一 parent：`2cb355812df2af5c77106056152d3d93e86784b9`。
  本轮文档存在单独分支；文档提交及其 tree 不继承此代码候选的测试资格。

## 2. 最新改动与已经具备的证据

N49D 给现有 MCP search 加可选目录 uri；源码能力、来源授权和无 uri 兼容边界见
[N49D 计划](docs/nodes/N49D-PLAN.md)及[用法](docs/integration/MCP-DIRECTORY-SEARCH.md)。

PR69 将 Windows wrapper 自测的五处契约预算由 20 秒改为 60 秒；外层自测阶段预算
仍为 120 秒，故意使用 20.0 的错误类型反例保留。不要把 60 秒修复解释为原生运行已通过。

必须区分两种 diff：与已发布 v2 tree `84ed60130049e872d489b7bb920a76dc3cd7bb96`
直接比较，只变一文件的五处预算；GitHub PR 的 merge-base 比较有三文件、78 行新增 / 42 行删除，
还包括 ancestry 固定值与 workflow fetch-depth。两分支在 parent `2cb3558…` 处分叉，
并非 head 在 base 上简单追加。因此不能将 PR 整体描述成仅五行的一文件变更。

PR69 描述报告 normal 和 optimized Python 均为 `passed=true, 1292 controls`。
这是既有本地控制结果，本次只核对来源和源码身份，未重跑、不称为全套 native PASS。
可访问 timeout 工作副本的测试文件 blob 为 `9527a0bfaf837aabdd492872024869f87e2317be`，
与远端冻结候选一致；其 25 个实际源码/文档文件均匹配。旧工作副本和缓存未被盲目推送。

## 3. 仍缺什么

精确 head 的全事件 Actions 查询 `total_count=0`；check-runs 为 0，commit statuses 为空，
PR reviews 和讨论为空。空结果不是成功。N49D outcome 仍为
[PENDING](docs/nodes/N49D-HARD-AUDIT.md)，[RESULT](docs/nodes/n49d-evidence/RESULT.json)
仍明确 `qualification_passed=false`。

下一步是固定 SHA/tree 的四个 native job：linux-cmake、windows-cmake、windows-msvc、
linux-sanitizers；保存完整原始工件并独立回读，然后由真实独立审查者对该代码候选完成 outcome review。
Windows 必须实际执行 wrapper、HTTP、canonical suites 和 strict RunOnly；Linux 或静态控制不能代替。
当前 workflow 只在指定 feature 分支 push 或 workflow_dispatch 触发，PR 本身不会自动获得这四项验证。
此次没有启动 CI、改变候选分支或改写任何 pending 审计。

项目整体仍未结项：真实已登录客户端后续记忆消费、真实模型质量和全流程费用、其余 PG 对等、
用户 Windows 11、签名与稳定发行、Issue40 分别保留。Windows Server CI 不等于用户 Windows 11。
公开旧包不能验证 N49D；此次没有新包、发行资产替换、真实数据测试或付费模型调用。
