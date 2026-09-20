# 原子批量使用回执（N47Z）

一个批次在同一来源内上报或撤回多条使用记录，先只读预览，再明确执行。成功时整批
提交；任一条校验、写入或提交失败时，回执变更全部回滚。不需要新增表或后台服务。
当前需要含N47Z的新源码构建，公开N47X包不含本模块；本轮没有替换安装包。

## 接口与边界

| 操作 | CLI | 现有MCP路由 |
| --- | --- | --- |
| 只读预览 | fact usage-batch-preview | memory_read，view=usage_batch，payload为JSON字符串 |
| 明确执行 | fact usage-batch-apply | memory_write，action=fact_usage_batch，payload含snapshot |

payload的operation为report或revoke，不混用；items为1–32条、最多8个事实，usage_id
不得重复。report项包含fact_id、usage_id、expected_revision；revoke项只含两个ID。
ID都是64位小写十六进制。MCP来源/写权限不变，预览成功不代表获得写入许可。
JSON输入最多8192字节，结果最多16384字节（包括CLI换行，不含MCP协议外壳）。

正常回执仍表示调用方声称使用，绝非真实模型消费、用户确认或事实真实性证明。
不会自动调整排序、置信度或衰减。原有单条命令保持可用。

## 先预览，再执行

以下两个PowerShell块应分开执行。先替换已有事实ID、实际revision和程序路径；同一次
使用的usage_id由调用方生成并保留，不能因网络错误就悄悄换ID重复上报。

```powershell
$ErrorActionPreference = 'Stop'
$exe = (Resolve-Path '.\build\cl\qbrain.exe').Path
$brain = 'my-brain'
$source = 'default'
$usageId = [Guid]::NewGuid().ToString('N') + [Guid]::NewGuid().ToString('N')
$spec = @{ operation = 'report'; items = @(@{
    fact_id = '<实际64位fact_id>'
    usage_id = $usageId
    expected_revision = 1 # 替换为实际读取的版本
}) }
$r = & '.\scripts\Invoke-QbrainJson.ps1' -FilePath $exe -ArgumentList @('fact','usage-batch-preview','--brain',$brain,'--source',$source) -InputJson ($spec | ConvertTo-Json -Depth 6 -Compress)
if ($r.ExitCode -ne 0) { throw $r.Stdout }
$preview = $r.Stdout | ConvertFrom-Json
$preview | ConvertTo-Json -Depth 6
```

确认items和would_change符合预期，再显式执行原计划：

```powershell
$approved = @{ operation = $spec.operation; items = $spec.items; snapshot = $preview.snapshot }
$r = & '.\scripts\Invoke-QbrainJson.ps1' -FilePath $exe -ArgumentList @('fact','usage-batch-apply','--brain',$brain,'--source',$source) -InputJson ($approved | ConvertTo-Json -Depth 6 -Compress)
if ($r.ExitCode -ne 0) { throw $r.Stdout }
$r.Stdout
```

批量撤回时把operation换为revoke，items只保留fact_id和usage_id，重新预览。不要把
expected_revision带入revoke项。上述说明按接口复核，并非宣称在用户本机执行过。

## 预览结果、并发变化与重试

items按usage_id排序，action为report、already_reported、revoke或already_withdrawn。
will_change说明该项是否需要变更；would_change是预期变更数，unchanged是无需变更
的项数。预览changed=0；执行成功changed=would_change。同一批次的新上报使用同一
时间，重复上报或撤回不改写原有时间。输入重排不改变选择或指纹。

snapshot绑定来源、操作、完整选择、所选事实版本和全部有界回执集合。相关新增、
撤回或版本变化会使旧批准失效，即使变化的行未被本批次选中。返回
fact_usage_batch_snapshot_conflict时，应重新预览和检查，不拼接旧结果或自动重试。

实际成功变更后，旧snapshot也失效。网络结果不确定时，重新预览原来的ID：已经完成
的记录会显示already_reported/already_withdrawn，重新明确执行只做剩余变化。
这不是持久化的批次请求日志，也不认证远端“恰好一次”投递。

## 权限、数据有效性与事务所有权

新上报仍要求事实活动、支持证据有效、未归档且版本精确匹配。已撤回ID不能复活。
合法的过期、归档或已退休事实仍保留撤回权。继承N47Y完整性校验和每事实4096条
容量（包含撤回墓碑），不自动清洗损坏记录或驱逐旧记录。最后支持遗忘时仍级联清理。

直接C++调用时，apply必须拥有事务：显式BEGIN/SAVEPOINT、未结束SELECT、
INSERT RETURNING、BLOB句柄或附加数据库上的事务都会触发fact_transaction_active。
模块不会替调用方提交、回滚、重置或结束语句；应由调用方先结束自己的事务。
只读preview可以在调用方事务中执行。不要把“autocommit为真”当作连接完全空闲。

## 原子性不覆盖哪些事情

首次有效上报需要沿用原使用模块初始化及预先备份。初始化与回执变更不是同一事务；
竞争发生时可能留下空模块与备份，但不会留下半个批次的回执。正常预览不建模块、
不写记录；继承CLI打开脑库的通用行为没有修改。

本功能不保证物理断电/磁盘损坏、敌意管理员/触发器或同一连接无同步并发使用下的
安全；不安全擦除WAL或备份，不自动修复数据库。观察和预览不是永久有效性保证。
真实模型/客户端、PG对等和Issue40历史超时根因仍是独立未完成项。
