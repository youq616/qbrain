# Qbrain

Windows 原生 C++20 / PowerShell Agent 记忆与知识库，默认 SQLite + FTS5。
不要求 Docker、WSL 或 Python 服务。由 Lordakee/qbrain 的 MIT 代码继续开发；
gbrain / OpenViking 是设计参考，不表示完整功能等价。

## 当前开发预览：N47H

[仓库 Release：candidates-preview-80fe1b9d](https://github.com/youq616/qbrain/releases/tag/candidates-preview-80fe1b9d)
选择 `qbrain-windows-x64-candidates.zip` 并完整解压。ZIP SHA256：
`6d4747d0332fc39e45a5ca4b2e815ee01e135959b97722ae92287dbaa14508cd`。
原CI测试字节、未重打包、未签名，不是整个项目的最终发行。实际产品源码
`80fe1b9d31de6cc41d06be6db0e1035c1a747eb7`，
[PR #24](https://github.com/youq616/qbrain/pull/24) 已合并。
用MANIFEST、完整源码SHA和外部摘要识别版本，不以旧dist或旧固定哈希入口替代。

[当前状态](CURRENT-STATUS.md) · [阶段审核](docs/nodes/N47H-HARD-AUDIT.md) ·
[测试摘要](docs/nodes/n47h-evidence/SUMMARY.json) · [发布记录](docs/nodes/n47h-evidence/RELEASE.json)

## N47H：分页发现候选，再明确决定如何整理

`fact candidates`与既有`memory_read(view=lifecycle_candidates)`只读发现当前来源
的维护候选：archive为有效active、未归档、最新有效支持达到年龄阈值的事实；
restore为有效active已归档事实。年龄不是使用频率、用户确认或可信度。
结果只返回metadata与N47G批量输入，不复制原话、不自动归档或恢复。

```powershell
.\qbrain.exe fact candidates --brain my-brain --source my-project --operation archive --stale-after-days 180 --limit 10 --max-bytes 8192
.\qbrain.exe fact candidates --brain my-brain --source my-project --operation restore --limit 10 --max-bytes 8192
```

每页最多检查100个原始候选、输出32项；按fact_id寻址，续查传上一页next_after_id
为after_id。预算中断不跳过未返回的当前事实。空页不等于扫描结束；has_more=true
可能仍有后续。progressed=false应提高预算或明确停止，不要无条件重复请求。
每页单快照，不是跨页原子全库快照；较小ID的新变化需重新扫描。cursor不代表权限。
[完整查询、分页和批量衔接说明](docs/integration/LIFECYCLE-CANDIDATES.zh-CN.md)。

## N47G：先预检，再原子化批量归档／恢复

`fact batch-preview`只读检查1..32个显式同来源事实；`fact batch-apply`明确执行。
候选响应的batch_payload对象可作为输入，每项只有fact_id和当前expected_revision。
预检不会锁定版本或写入，after预测不是许可；apply会在单事务内重验全部项目。
任何事实失效、版本变化或数据库提交失败都整批拒绝，不留下前半批成功。

```json
{"operation":"archive","items":[{"fact_id":"<真实64位事实ID>","expected_revision":3}]}
```

示例占位符不可直接执行；通过同包UTF-8脚本将真实JSON传入stdin。MCP沿用
`memory_read(view=lifecycle_batch,payload=...)`和
`memory_write(action=fact_lifecycle_batch,payload=...)`，payload为JSON字符串。
重复ID／JSON键、错类型和无关字段拒绝；读接口不能被apply／force参数提升为写入。
[批量调用和事务边界](docs/integration/BATCH-LIFECYCLE.zh-CN.md)。

## N47F：可撤销归档，不隐藏反证

原单条`fact archive`／`fact restore`保持。归档不修改原话、证据或退休状态，
仅限制默认事实召回／已开启事实Hook的命中入口；有效直接反证仍须保留，显式
read/conflicts仍可查看。归档不是遗忘、保密或安全擦除；旧二进制不认识归档策略。
恢复不能复活撤回、替代、过期、遗忘或损坏内容。

首次磁盘归档模块初始化先备份。准备和策略应用分开，应用失败可能留备份／空表，
但不会部分提交策略和版本。元数据不复制原话，最后证据删除后级联清理。
`fact lifecycle`／`memory_read(view=lifecycle)`的年龄来自最新有效支持created_at，
不是最后使用时间。异常时间unknown/null，未来时间clock_anomaly，不自动归档。
[单条生命周期与降级边界](docs/integration/FACT-LIFECYCLE.zh-CN.md)。

## 自动采集、整理与召回

N47E的`-EnableFactPromotion`独立默认关闭，要求`-EnableCapture`；N47D事实召回需要
独立`-EnableFactRecall`。明确开启后，本地规则提取的完整用户原话整理为证据绑定
事实，固定memory.<category>标签、confidence=null，不推断真假或语义冲突。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Install-QbrainMemory.ps1 -HostName Claude -ProjectPath "D:\Projects\MyProject" -Binary ".\qbrain.exe" -EnableCapture -EnableFactPromotion -EnableFactRecall
```

仅普通采集不传事实开关；仅召回可不采集。重装不传开关即关闭；卸载保留脑库和
备份，关闭不撤销旧事实。同原话独立支持可追加，重放不增版本；退休事实不自动
复活，新支持不清除归档。归档不绕过证据或批次限额。
[本地整理](docs/integration/LOCAL-FACT-PROMOTION.zh-CN.md) ·
[Hook响应预算](docs/integration/HOOK-FACT-RECALL.zh-CN.md)。

N47A证据生命周期、N47B成对冲突、N47C含直接反证召回保持。会话原文、来源隔离、
采集开关、去重、遗忘联动、项目Hook与可撤销安装、L0/L1摘录、独立许可摘要、L2分页、
缓存失效、六工具MCP、CJK子串、精确向量候选、Embedding标签隔离、批量队列与过期
结果拒绝保持。系统代理设置改变后须重启使用HTTP的进程。

## 验证和限制

原生35111907426／35111907432通过：Windows56注册组；候选17场景647断言在两Windows、
portable和Linux ASan+UBSan通过；实际CLI/MCP43检查63次预期退出。原N47A-G、HTTP、
队列、CJK、记忆、Hook、上下文和双PowerShell保留；真实PG DSN仍明确SKIP-PG。

阶段单独工程自审重新GCC构建并执行候选和旧批量／生命周期，141报告／注册门槛及
254原始源码／日志／包回读通过。独立参考模型覆盖288混合状态事实、46遍历／695页；
错误推进游标的临时副本准确触发失败。证据归档在n47h-evidence，未改变产品字节。
本阶段无未解决P0/P1，不是绝对无bug承诺、第三方审核或新的真实客户端验收。

用户转交N47E Claude自动链路通过摘要，与本轮程序测试分开；不用Claude结果替代
仍受认证阻塞的Codex。**Hook上下文交给已授权客户端，客户端可能发送给模型。**
没有新Qbrain请求不代表没有客户端外发。forget不是备份/WAL/旧上下文安全擦除；
哈希不是签名。数量和证据限额不保证SQL或备份I/O耗时，候选及预检可能过时。

通用语义合并／冲突推断、使用确认计数、自动衰减、画像、百万事件性能、PG对等、
完整ACL/DLP、模型质量费用和正式签名仍未完成。候选发现不等于自动维护或项目完成。

## 从源码构建与数据

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-cl.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-tests-cl.ps1 -SkipProductionBuild
```

源码构建需要MSVC；仅同轮生产构建成功且源码未变时跳过重复构建。运行预编译包
无需编译器；Python是测试工具依赖。升级前备份脑库，默认数据为
`%LOCALAPPDATA%\Qbrain\`。不上传真实密钥／个人聊天，不绕过客户端信任。
[安装卸载](docs/integration/QUICKSTART.zh-CN.md) · [接入说明](docs/integration/WINDOWS-MEMORY.md) ·
[本地Agent单提示词交接](LOCAL-AGENT-HANDOFF.md)。

历史报告和失败保留，[Issue #2](https://github.com/youq616/qbrain/issues/2)跟踪总路线。
MIT；保留[LICENSE](LICENSE)和[第三方说明](THIRD-PARTY-NOTICES.md)。
