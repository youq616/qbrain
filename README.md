# Qbrain

Windows 原生 C++20 / PowerShell Agent 记忆与知识库，默认 SQLite + FTS5。
不要求 Docker、WSL 或 Python 服务。由 Lordakee/qbrain 的 MIT 代码继续开发；
gbrain / OpenViking 是设计参考，不表示完整功能等价。

## 当前开发预览：N47F

[仓库 Release：lifecycle-preview-cafb4866](https://github.com/youq616/qbrain/releases/tag/lifecycle-preview-cafb4866)
选择 `qbrain-windows-x64-lifecycle.zip`，完整解压。ZIP SHA256：
`c16f15a7ad318beb58059b05d3f400399b33d34c000d040c3c1ddcc179641f55`。
原CI测试字节，未重打包、未签名，不是整个项目完成的正式发行。
实际产品源码 `cafb48667177002ae6ea0f1976eea2f388826024`，
[PR #22](https://github.com/youq616/qbrain/pull/22) 已合并。
用 MANIFEST、完整源码 SHA 和外部摘要识别版本，不以历史dist或旧固定哈希入口替代。

[当前状态](CURRENT-STATUS.md) · [阶段审核](docs/nodes/N47F-HARD-AUDIT.md) ·
[测试摘要](docs/nodes/n47f-evidence/SUMMARY.json) · [发布记录](docs/nodes/n47f-evidence/RELEASE.json)

## N47F：可撤销归档，不隐藏冲突证据

`fact archive` / `fact restore` 使用当前 `expected_revision` 显式改变事实召回策略，
不改原话、证据或退休状态。归档事实不作为默认fact recall和已开启事实Hook的命中
入口，但必须保留为其他命中的有效直接反证。显式fact read/conflicts仍可检查。
归档不是遗忘、保密屏障或安全擦除；旧版本也不认识归档策略，降级可能重新召回。

恢复要求事实仍active且有有效完整证据，不能复活撤回、替代、过期、遗忘或损坏内容。
首次磁盘归档模块初始化先备份，元数据无原话副本，最后证据删除后级联清理。
表准备和归档交易是两个步骤；失败可能留备份/空表，不留下半次状态更新。

```powershell
.\qbrain.exe fact lifecycle --brain my-brain --source my-project --stale-after-days 180 --limit 10 --max-bytes 8192
```

`fact lifecycle` / `memory_read(view=lifecycle)` 只读提供年龄提醒；年龄来自有效支持
的最新created_at，不是使用频率、用户确认时间或可信度。stale不是新的事实status，
不会自动归档。无效时间为unknown/null，未来时间为clock_anomaly。
[完整归档、恢复与降级说明](docs/integration/FACT-LIFECYCLE.zh-CN.md)。

## 自动采集、整理与召回

N47E的`-EnableFactPromotion`独立默认关闭，要求`-EnableCapture`；N47D事实召回需要
独立的`-EnableFactRecall`。开启后本地规则提取的完整用户原话成为证据绑定事实，
固定memory.<category>标签、confidence=null，不推断真假或自动语义矛盾。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Install-QbrainMemory.ps1 -HostName Claude -ProjectPath "D:\Projects\MyProject" -Binary ".\qbrain.exe" -EnableCapture -EnableFactPromotion -EnableFactRecall
```

只要普通采集就不传两个事实开关；仅召回可不采集。重装不传开关即关闭，卸载保留
脑库/备份，关闭不撤销旧事实。相同独立原话追加支持，重放不增版本；退休事实不会
被自动复活。16条物理支持及每批上限照旧，不因归档恢复绕过。
[本地整理](docs/integration/LOCAL-FACT-PROMOTION.zh-CN.md) ·
[Hook统一响应预算](docs/integration/HOOK-FACT-RECALL.zh-CN.md)。

N47A事实生命周期、N47B成对冲突读取、N47C带直接反证的主动召回保持。会话原文、
来源隔离、采集开关、重试去重、遗忘联动、项目Hook与可撤销安装，L0/L1摘录、独立
许可的可选摘要、L2分页、缓存失效、六工具MCP、CJK子串、精确向量候选、Embedding
标签隔离、批量队列及过期结果拒绝均保留。系统代理改变后需重启HTTP使用进程。

## 验证和限制

修复版原生35076641849/35076641751通过：Windows54注册组；生命周期17场景180断言
在两套Windows及portable通过，36检查58次预期进程退出。旧事实/冲突/召回/Hook/
自动整理/HTTP/队列/CJK/记忆和双PowerShell回归保留，真实PG DSN明确SKIP。

ASan+UBSan独立Linux执行35077139073通过；单独工程复核又重新GCC构建并执行新增
生命周期、旧召回和进程专项，111报告门槛及212原始源码/日志/包回读通过。早期
只读事务授权及时间类型缺陷已修复、失败记录保留。未发现本阶段未解决P0/P1，
但不是绝对无bug保证、第三方审核、Windows sanitizer或新的已登录宿主验收。

用户已转交N47E Claude实机自动链路通过摘要，不要求重复同一任务；原报告与本次
N47F合成验证分开记录。既有Codex认证阻塞保持独立，不用Claude结果代替。

**Hook上下文会交给已授权客户端，客户端可能发送给模型。** 没有额外Qbrain请求
不等于没有客户端外发。逐事件forget不安全擦除备份、WAL、旧上下文或其他独立同句
事件；哈希是本地一致性检查，不是签名。预算不是全会话Token或SQL耗时保证。

自动语义合并/冲突推断、使用计数、自动衰减、画像、百万事件性能、PG对等、完整
ACL/DLP、模型质量费用和正式签名发行仍未完成。N47F仅交付上述可审查生命周期切片。

## 从源码构建与数据

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-cl.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-tests-cl.ps1 -SkipProductionBuild
```

源码构建需要MSVC；只在本轮生产构建成功且源码未变时跳过重复构建。预编译产品不
要求编译器，Python仅为测试工具依赖。升级前备份脑库，默认数据位于
`%LOCALAPPDATA%\Qbrain\`。不读取/上传真实密钥或个人聊天，不绕过客户端信任。
[安装卸载](docs/integration/QUICKSTART.zh-CN.md) · [接入边界](docs/integration/WINDOWS-MEMORY.md) ·
[本地Agent单提示词交接](LOCAL-AGENT-HANDOFF.md)。

历史阶段报告和失败保留，[Issue #2](https://github.com/youq616/qbrain/issues/2)跟踪总路线。
MIT；保留[LICENSE](LICENSE)与[第三方说明](THIRD-PARTY-NOTICES.md)。
