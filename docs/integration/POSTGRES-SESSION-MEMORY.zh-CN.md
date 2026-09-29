# N48O：PostgreSQL 会话记忆采集、提取、召回与遗忘

更新：2026-09-29。固定受测源码 `504f2825fe371d3a1b4a867c11f1b66b16a3bc8a`。
本模块接续 PR57；最终合并身份以 PR 和交付记录为准。程序仍为未签名开发候选，
不是稳定版或自动安装器。本轮没有替换公开 N47X、旧 N48K/N48M 等固定运行包。

## 已完成的范围

现有 `memory capture / extract / read / status / drain / forget` 可以使用显式配置的
PostgreSQL 数据库。SQLite 仍是默认后端；只有配置 `QBRAIN_PG_DSN` 才选用 PostgreSQL。
不会自动迁移 SQLite 内容，也不代表 fact_store、context、Hook 或所有接口已完成 PG 对等。

归档保存会话原文与来源。提取保留完整用户消息、原始位置、事件和有效期；助手、工具、
未知角色不会自动变为用户事实。返回值标记为调用方提供的用户陈述和不可信数据，不认证
身份、真伪或模型实际消费，不把陈述升级成系统指令。没有自动提升置信度、语义覆盖或
模型推断转事实的新机制。默认本地提取是明确语句规则，不是通用语义理解。

同一来源/会话/片段重复提交保持幂等；同片段不同内容拒绝覆盖。过期、已改写或撤销的
证据不能继续发布记忆。遗忘删除该事件拥有的记忆并保留墓碑，重放旧片段不会复活。
另一事件独立保存的相同陈述不因只遗忘一份来源而消失。遗忘不是 WAL/备份的物理擦除。

## 隔离与安全边界

**同一个 DSN 下更换 `--brain` 标签，不会创建另一套 PostgreSQL 表或独立租户。**
数据位于指定数据库的 `public` 模式；`--source` 是应用逻辑来源，不是行级安全或数据库
授权。需要人员/项目硬隔离时，使用分别授权的数据库与角色，不仅改 brain/source 名称。
MCP 默认拒绝写入及来源许可保持原规则，CLI 操作要求操作者已有相应授权。

PG 连接可能向远程服务器发送记忆，不能说数据始终只留本机。TLS、服务器访问控制、
备份、保留期和密钥保管由操作者配置；不得把真实 DSN、密码或私人会话提交到代码仓库。
首次试用选择专用测试数据库，生产库应先备份。不得对生产库运行 `.ci` 测试脚本，
这些测试会重建一次性合成测试库；它们不是维护/修复命令。

## Windows 依赖与启动

Windows x64 程序无需 Docker、WSL 或 Python 常驻服务。PG 功能需要兼容的原生
PostgreSQL 服务、libpq 及其依赖；Visual C++ x64 运行库也必须可用。小程序包不捆绑
服务器或第三方 DLL。请使用可信 PostgreSQL 安装提供的运行库，不从不明网站逐个下载 DLL。
libpq 为延迟加载，默认 SQLite 路径不主动使用 PG 服务。完整依赖原件保留在 CI 证据中，
不能把证据目录当成经过许可清理的安装包。版本以交付记录的 EXE SHA256 为准。

服务器要求 UTF8，当前可识别模式为 public，核心结构为既有 v13。首次有效写入会原子
创建四张可选表 memory_module/events/items/attempts，模块版本1，时间和引用为 BIGINT。
读取未初始化模块、跳过未授权自动采集不创建这些可选表；原有应用启动仍可能初始化
核心表或创建本地目录，不能声称整个进程无副作用。

## 一次明确授权的合成演示

先在安全位置设置**当前进程的测试库** `QBRAIN_PG_DSN`，并使受信任的 libpq 可加载。
下面不配置密码、不启用自动采集、不调用模型；只保存和处理包内合成会话。使用已有
UTF-8 桥接脚本避免 PowerShell 5.1 管道编码损坏中文。在独立解压的工具包目录执行：

```powershell
$ErrorActionPreference = 'Stop'
if ([string]::IsNullOrWhiteSpace($env:QBRAIN_PG_DSN)) {
    throw '先安全配置明确授权的测试 PostgreSQL 连接；未配置时默认是 SQLite。'
}
$exe = (Resolve-Path -LiteralPath '.\qbrain.exe').ProviderPath
$bridge = (Resolve-Path -LiteralPath '.\Invoke-QbrainJson.ps1').ProviderPath
$sample = (Resolve-Path -LiteralPath '.\samples\session.synthetic.json').ProviderPath
$utf8 = New-Object System.Text.UTF8Encoding($false, $true)
$payload = [System.IO.File]::ReadAllText($sample, $utf8)
function Invoke-MemoryDemo([string[]]$ArgsForQbrain, [string]$JsonInput = '') {
    $r = & $bridge -FilePath $exe -ArgumentList $ArgsForQbrain -InputJson $JsonInput
    if ($r.ExitCode -ne 0) { throw ('Qbrain rejected the operation: ' + $r.Stdout) }
    return ($r.Stdout | ConvertFrom-Json)
}
$capture = Invoke-MemoryDemo -ArgsForQbrain @('memory','capture','--manual','--source','default','--brain','pg-demo') -JsonInput $payload
if ([string]::IsNullOrWhiteSpace($capture.event_id)) { throw '没有有效事件 ID，停止。' }
$eventId = $capture.event_id
Invoke-MemoryDemo -ArgsForQbrain @('memory','extract','--event',$eventId,'--source','default','--brain','pg-demo')
Invoke-MemoryDemo -ArgsForQbrain @('memory','read','--query','Windows','--source','default','--brain','pg-demo')
Invoke-MemoryDemo -ArgsForQbrain @('memory','status','--event',$eventId,'--source','default','--brain','pg-demo')
```

`--manual` 只授权本次归档，不开启后续自动采集。默认 extract 使用本地规则；外部
模型提取还需单独许可。状态可能包含未知用量/费用，不得当作零。保管本次返回的事件ID，
结束合成测试时只遗忘这个事件，不要替换成别人的ID：

```powershell
Invoke-MemoryDemo -ArgsForQbrain @('memory','forget','--event',$eventId,'--source','default','--brain','pg-demo')
```

原样重跑已遗忘片段会被墓碑抑制，这是预期行为。新测试需明确创建新的会话/片段身份，
不能把新身份当成“原撤销失效”。在仓库使用时对应样本为 examples/memory/session.synthetic.json，
桥为 scripts/Invoke-QbrainJson.ps1，程序位于实际构建目录。PowerShell 整段示例没有在
用户电脑执行；实际 Windows/PG 命令验收和本地示例的执行范围见结果报告。

## 事务、并发和拒绝原因

写入使用短 READ COMMITTED 事务，按固定顺序锁 public.sources/pages/config，事务内
锁等待预算2500ms。表级串行化是保守的一致性措施，不是高吞吐保证。锁错误回滚，
不会自动重试付费模型请求。已有调用方事务（包括失败事务）拒绝加入，不会顺便提交它。

外部模型调用前释放锁；返回后重新检查来源证据、租约、遗忘状态、采集和外发许可。
旧候选 ed79 的临时表遮蔽缺陷已由 cd4 修复：七个表名有效解析OID必须等于 public 对象，
入口及回调后都会核对。不改 search_path、不删调用方临时表。该历史反例是同连接
临时表场景，不是已证明发生的远程攻击或用户事故。

`memory_transaction_active` 表示调用方事务仍在；`memory_pg_schema_context` 表示
public/UTF8/表解析范围不兼容；`memory_schema_version_unsupported` 表示可选表布局
或版本不支持。不要手改版本标记、删除表或放宽断言以隐藏错误。召回采用 ASCII
大小写不敏感的字面匹配，其他 Unicode 不做额外大小写折叠；不是全文语义搜索承诺。

N48M/N48N 仅操作 SQLite 文件，不适用于 DSN。PG 使用相应管理员备份恢复流程。
退出 PG opt-in 或回退程序不会自动删除已经创建的表，本模块没有一键删除生产数据脚本。

## 完整源码与结果绑定

本次整合前后均固定 Git 源码树、全部文件清单、归档和程序摘要，采用v2预检记录；
旧v1记录不会自动获得新结论。Windows只在完整文件哈希匹配时接受受限文本换行变化，
不盲目转写二进制。结果审核重新计算事件、引文、命令与错误语义，而非只看PASS字段。
历史 `.ci/check_pg_memory_evidence.py` 的独立CLI仍固定旧候选，不要拿它直接验证新EXE；
当前候选使用 `.ci/run_pg_memory_gate.py verify` 及测试前另行保存的校验摘要。
这些哈希不能认证作者、服务器、二进制构建过程或全部工具协同替换；不是恶意文件沙箱。

[完整分离自审](../nodes/N48O-HARD-AUDIT.md) ·
[固定源码结果](../nodes/n48o-evidence/FINAL-RESULT.json) ·
[项目当前状态](../../CURRENT-STATUS.md)。真实客户端后续消费、真实模型质量/全流程费用、
剩余 PG 模块、签名、稳定版和 Issue40 均仍需独立验收。
