# 使用回执逐条查询与安全分页（N47U）

N47T 提供上报、撤回和汇总；N47U 补齐逐条查询，便于找出实际 usage_id，再决定是否
调用已有的 revoke-use。新命令需要包含 N47U 的源码构建，当前 N47R 公开包不含它。
本说明不是要求用户现在重新安装；本阶段没有替换 Release 或安装器。

## 查询结果与筛选

```powershell
.\build\cl\qbrain.exe fact usage-list --brain my-brain --source default --id '<实际64位fact_id>' --state all --limit 25 --max-bytes 8192
```

--state 可选 all、current、historical、withdrawn，缺省 all。current 是未撤回且绑定
当前事实版本；historical 是未撤回但属于旧版本；withdrawn 包含各版本已撤回记录。
每项只返回 usage_id、fact_revision、reported_at、withdrawn_at 和 state，不返回原话
或会话。记录按 usage_id 升序排列，不按上报时间排序。时间是 UTC Unix 秒。

matched_receipts 是整个筛选集合的条数，不是本页条数或剩余条数；items 才是本页。
每页 --limit 为 1–50；--max-bytes 为 512–32768，计算返回 JSON 的 UTF-8 字节并包含
CLI 末尾换行。MCP 外层协议、JSON 字符串转义的额外字节不包含在这个结果预算内。
不能完整放入一条记录时返回 fact_usage_byte_budget，而不是空页加不推进的游标。
提高字节预算再重试；即使空集合，预算也必须能容纳完整元数据外壳。

MCP 使用现有 memory_read，view=usage_receipts、fact_id；筛选字段叫 receipt_state，
分页字段为 after_id 和 snapshot，并接受 limit、max_bytes、source_id。它不会增加
工具名称，不要求写权限，也不会因为发现了回执就自动授予撤回权限。

## 翻页期间数据变化时，丢弃部分结果并重新开始

首页不带 --after-id/--snapshot。若 has_more=true，把 next_after_id 和原 snapshot
同时传到下一页。后续可以调整每页数量和字节预算，不能切换事实、来源或筛选条件。
末页 has_more=false、next_after_id=null；没有更多数据时正常停止。

snapshot 是当前数据指纹，绑定来源、事实、事实版本、归档/模块初始化状态、筛选和
该事实完整的有界回执集合。中途新增回执、撤回（即使不在当前筛选内）或事实版本
变化，旧分页会返回 fact_usage_snapshot_conflict。应放弃这次已收集的部分结果，
重新从首页查询，不能把新旧页混在一起，也不要无限自动重试。

这不是跨请求锁、签名、登录凭证或永久快照。每次请求重新验证来源权限和事实的
完整有效证据。过期、已退休或已遗忘的事实不能通过旧游标继续曝光。普通幂等重试
没有改变记录时不破坏指纹。模块已初始化后，其他事实的普通使用写入不影响此集合。
外部恢复旧数据库或恶意管理员回滚历史不在指纹保障范围内。

## 一次收集完整列表的 PowerShell 示例

在完整源码根目录运行下段，先替换脑库与实际事实 ID。直到所有页成功才展示结果；
任一页冲突或出错会停止，不自动撤回记录，也不调用模型。

```powershell
$ErrorActionPreference = 'Stop'
$exe = (Resolve-Path '.\build\cl\qbrain.exe').Path
$brain = 'my-brain'
$source = 'default'
$factId = '<实际64位fact_id>'
$filter = 'all'
$all = New-Object System.Collections.ArrayList
$seen = New-Object 'System.Collections.Generic.HashSet[string]'
$after = $null
$snapshot = $null
$pages = 0
while ($true) {
    $argv = @('fact','usage-list','--brain',$brain,'--source',$source,'--id',$factId,'--state',$filter,'--limit','25','--max-bytes','8192')
    if ($null -ne $after) { $argv += @('--after-id',$after,'--snapshot',$snapshot) }
    $r = & '.\scripts\Invoke-QbrainJson.ps1' -FilePath $exe -ArgumentList $argv -InputJson ''
    if ($r.ExitCode -ne 0) { throw ('Discard this partial audit and inspect the error: ' + $r.Stdout) }
    $page = $r.Stdout | ConvertFrom-Json
    if ($null -eq $snapshot) { $snapshot = $page.snapshot }
    if ($snapshot -cne $page.snapshot) { throw 'Snapshot changed; discard partial results.' }
    $pages++
    if ($pages -gt 4096) { throw 'Page limit exceeded.' }
    foreach ($item in @($page.items)) {
        if (-not $seen.Add([string]$item.usage_id)) { throw 'Duplicate receipt across pages.' }
        [void]$all.Add($item)
    }
    if (-not $page.has_more) { break }
    if (@($page.items).Count -eq 0 -or -not $page.next_after_id) { throw 'Cursor did not advance.' }
    $after = [string]$page.next_after_id
}
$all | Format-Table usage_id, fact_revision, state, reported_at, withdrawn_at -AutoSize
```

此例采用已存在的 UTF-8 字节桥，参数及输出按实际接口复核；本阶段没有把这段新增
文档命令声明为另一轮已执行的 Windows 安装测试。直接 CLI 的分页/预算行为已在
Windows 和 Linux 新构建程序上测试。

## 只读与数据保留边界

查询本身不新增回执、创建 N47T 可选模块、生成备份、改变事实版本或写 Hook 检查点。
这是已有脑库上的操作保证；原 CLI 打开/初始化脑库的通用行为没有在本功能中改写。
每页先校验完整集合再筛选，损坏的页外记录不会被藏起来。每个事实最多扫描 4097
条用于执行既有 4096 条上限检查，超过上限拒绝，不返回部分可信的审计。

归档仍有有效证据的事实可以查询，并标记 archived=true；这不重新开启召回。最后
支持遗忘后的级联删除保持不变；自然过期只影响资格，不代表备份/WAL 已安全擦除。
发现 ID 后，撤回仍须走原有 fact revoke-use 或有明确写权限的 memory_write。

所有结果仍为 origin=caller_reported、host_consumption_verified=false、
fact_truth_verified=false。这不是事实确认、真实客户端消费或衰减/排名信号。
参见 [原上报与撤回规则](FACT-USAGE.zh-CN.md)。SQLite-only；真实 PG、客户端/模型
效果、费用与稳定版最终验收不因这项功能完成。
