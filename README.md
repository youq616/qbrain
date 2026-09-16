# Qbrain

Windows 原生 C++20 / PowerShell Agent 记忆与知识库，默认 SQLite + FTS5。
不要求 Docker、WSL 或 Python 服务。由 Lordakee/qbrain 的 MIT 代码继续开发；
gbrain / OpenViking 是设计参考，不表示完整功能等价。

## 当前开发预览：N47G

[仓库 Release：batch-preview-b1292b54](https://github.com/youq616/qbrain/releases/tag/batch-preview-b1292b54)
选择 `qbrain-windows-x64-batch.zip`，完整解压。ZIP SHA256：
`85e0f15f907c2bf4ac39c6356d231637251209a902eb7fe6a50476161ae10603`。
原CI测试字节、未重打包、未签名，不是整个项目的最终发行。实际产品源码
`b1292b54543b9f54cd5e2b71f4ae4bf5f6247385`，
[PR #23](https://github.com/youq616/qbrain/pull/23) 已合并。
使用MANIFEST、完整源码SHA和外部摘要识别版本，不以旧dist或旧固定哈希入口替代。

[当前状态](CURRENT-STATUS.md) · [阶段审核](docs/nodes/N47G-HARD-AUDIT.md) ·
[测试摘要](docs/nodes/n47g-evidence/SUMMARY.json) · [发布记录](docs/nodes/n47g-evidence/RELEASE.json)

## N47G：先预检，再原子化批量归档／恢复

`fact batch-preview` 只读检查1..32个显式同来源事实；`fact batch-apply` 明确执行。
每项带fact_id和当前expected_revision。整批重新验证并在单事务提交，不是逐条提交
的循环：任何一个事实失效、版本变化或数据库报错，都不允许留下前半批成功。

```json
{
  "operation": "archive",
  "items": [
    {"fact_id": "<真实64位事实ID>", "expected_revision": 3},
    {"fact_id": "<另一真实64位事实ID>", "expected_revision": 7}
  ]
}
```

将同一输入JSON通过UTF-8 stdin交给相应命令；示例占位符不是可直接执行的ID。
预检结果中的预测after值不是新输入，也不是锁定版本或已经写入的证明。
MCP沿用 `memory_read(view=lifecycle_batch,payload=...)` 与
`memory_write(action=fact_lifecycle_batch,payload=...)`；payload是JSON字符串。
写默认拒绝、来源限制仍有效，读接口不能被payload中的apply/force提升为执行。
重复ID／JSON键、错类型和无关字段均拒绝。输入8KiB、完整元数据结果32KiB。
[完整调用、回滚与预检语义](docs/integration/BATCH-LIFECYCLE.zh-CN.md)。

## N47F：可撤销归档，不隐藏冲突证据

原有单条`fact archive`／`fact restore`保持。归档不改原话、证据或退休状态，
只限制默认fact recall／已开启事实Hook的命中入口。有效直接反证必须保留，显式
fact read/conflicts仍可检查。归档不是遗忘、保密或安全擦除；旧二进制不认识策略。
恢复不能复活已撤回、替代、过期、遗忘或损坏内容。

首次磁盘归档模块初始化先备份；元数据不复制原话，最后证据删除后级联清理。
准备和策略交易分开，失败可能留备份/空表，但不会留下部分策略或版本更新。
`fact lifecycle`／`memory_read(view=lifecycle)`只读提供年龄提醒；年龄来自有效支持
最新created_at，不是使用频率、确认时间或可信度。异常时间unknown/null，未来时间
clock_anomaly；不会自动归档。MCP的stale_after_days现在正确接入，旧视图仍拒绝它。
[单条归档及降级边界](docs/integration/FACT-LIFECYCLE.zh-CN.md)。

## 自动采集、整理与召回

N47E的`-EnableFactPromotion`独立默认关闭，要求`-EnableCapture`；N47D事实召回需要
独立的`-EnableFactRecall`。明确开启后，本地规则提取的完整用户原话整理为证据绑定
事实，固定memory.<category>标签、confidence=null，不推断真假或自动语义矛盾。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Install-QbrainMemory.ps1 -HostName Claude -ProjectPath "D:\Projects\MyProject" -Binary ".\qbrain.exe" -EnableCapture -EnableFactPromotion -EnableFactRecall
```

仅普通采集不传两个事实开关；仅召回可不采集。重装不传开关即关闭，卸载保留脑库
和备份，关闭不撤销旧事实。相同独立原话追加支持，重放不增版本；退休事实不会
自动复活，同一事实的新支持也不清除归档。证据和每批上限不会因归档被绕过。
[本地整理](docs/integration/LOCAL-FACT-PROMOTION.zh-CN.md) ·
[Hook完整响应预算](docs/integration/HOOK-FACT-RECALL.zh-CN.md)。

N47A证据生命周期、N47B成对冲突、N47C含直接反证召回保持。会话原文、来源隔离、
采集开关、重试去重、遗忘联动、项目Hook及可撤销安装、L0/L1摘录、独立许可的摘要、
L2分页、缓存失效、六工具MCP、CJK子串、精确向量候选、Embedding标签隔离、批量队列
与过期结果拒绝也保留。系统代理设置改变后需重启使用HTTP的进程。

## 验证与限制

原生35093371931／35093372100通过：Windows55注册组；批量15场景259断言在两Windows、
portable及Linux ASan+UBSan通过；实际CLI/MCP40检查54次预期退出。原N47A-F、HTTP、
队列、CJK、记忆、Hook、上下文和双PowerShell全部保留；真实PG DSN仍SKIP-PG。

单独工程自审又在Linux GCC14.2重新构建和执行新增批量、旧生命周期及进程专项；
31项报告/注册门槛，234项源码/日志/包回读，另有5场景67断言实际覆盖提交拒绝、
后续ABORT/FAIL/ROLLBACK和被真实读锁阻塞的COMMIT，全部通过。补充探针和原始报告
已归档。未发现本阶段未解决P0/P1，不是绝对无bug承诺、第三方审核或新的真实宿主验收。

用户已转交N47E Claude实机自动链路通过摘要；与N47G合成测试分开记录，不要求重复
同一任务，也不用Claude结果代替仍受认证阻塞的Codex客户端验收。
**Hook上下文会交给已授权客户端，客户端可能发送给模型。** 没有新增Qbrain请求不
表示没有客户端外发。逐事件forget不是备份/WAL/旧上下文安全擦除；哈希不是签名。
批量限额不等于备份I/O或SQL耗时保证。预检可能过时，执行必须重新检查。

通用语义合并/冲突推断、使用确认计数、自动衰减、画像、百万事件性能、PG对等、
完整ACL/DLP、模型质量费用和正式签名发行仍未完成。N47G仅完成显式批量管理切片。

## 从源码构建与数据

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-cl.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-tests-cl.ps1 -SkipProductionBuild
```

源码构建需要MSVC；仅在同轮生产构建成功且源码未变时跳过重复构建。预编译产品
不需要编译器；Python仅为测试工具依赖。升级前备份脑库，默认数据位于
`%LOCALAPPDATA%\Qbrain\`。不上传真实密钥或个人聊天，不绕过客户端信任。
[安装卸载](docs/integration/QUICKSTART.zh-CN.md) · [接入说明](docs/integration/WINDOWS-MEMORY.md) ·
[本地Agent单提示词交接](LOCAL-AGENT-HANDOFF.md)。

历史阶段报告和失败保留，[Issue #2](https://github.com/youq616/qbrain/issues/2)跟踪总路线。
MIT；保留[LICENSE](LICENSE)和[第三方说明](THIRD-PARTY-NOTICES.md)。
