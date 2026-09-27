# N48M：原生 SQLite 备份、校验与恢复到新目录

2026-09-27。新增 `qbrain backup create|verify|restore`。这是本地原生命令，
不需要 Python、Docker、WSL 或网络服务。旧 N48K 包和旧 N47X Release 不含此命令；
应使用本模块验收的程序或对应新源码构建，不要仅凭应用内部 2.0.0 版本号判断。

## 备份的内容及限制

本模块保存**明确指定的一个 SQLite 数据库，包含该库全部 source 的内容**。
事实、用量回执、撤销状态、数据库内配置及索引均随数据库复制；不是按单个 source
授权的导出操作，也不是 MCP 工具。它不会自动寻找或读取默认脑库。

**备份是明文、未加密的敏感文件。** 数据库内若存有敏感配置，也会包含在内；
SQLite 的空闲页可能保留已删除数据，本命令不做脱敏、压缩清理或密码加密。
不要把真实备份上传到公开仓库。Windows 输出继承目标父目录的权限，应选用仅授权
人员可访问的本地目录。命令不会替你配置 ACL、密钥管理或异地灾备。

不包括数据库外的文件附件、客户端配置、安装器事务、全局注册文件或外部模型凭据。
这不是整个 `%LOCALAPPDATA%\Qbrain\` 目录的备份，也不支持 PostgreSQL。
执行前应另外妥善保存这些文件；恢复本数据库不能独自恢复全部运行环境。

## 三个命令

```text
qbrain backup create --database PATH --output NEW_DIR [--timeout-ms 10000]
qbrain backup verify --backup DIR --expect-sha256 MANIFEST_SHA [--timeout-ms 10000]
qbrain backup restore --backup DIR --expect-sha256 MANIFEST_SHA --output NEW_DIR [--timeout-ms 10000]
```

参数采用独立的名字和值，不接受 `--overwrite`、重复参数、未定义参数或缺值。
备份、恢复的目标目录必须不存在，父目录必须已经存在。命令不会覆盖旧数据、递归
清理失败目录，或自动把恢复结果切换成默认脑库。程序运行身份需要有源文件读取权
与目标父目录写入权；只读 SQLite 连接仍可能需要访问 WAL/SHM 辅助文件。

成功退出码为 0，输出一条 `qbrain-backup-result-v1` JSON。拒绝或本地失败通常为
退出码 2，仅输出结构化 `error.code`。系统终止、断电等不能保证还会输出错误 JSON。
不要以“目录存在”判断成功；必须保存成功回执并重新校验。

## Windows PowerShell 完整操作示例

下面示例适用于 PowerShell 5.1/7。把 `my-brain` 和两个磁盘目录换成实际位置；
先创建好备份父目录和恢复父目录。不要指向真实脑库已有目录作为恢复目标。
这些命令由你主动执行才会操作本机；交付本身不会运行它们。

```powershell
$ErrorActionPreference = 'Stop'
$exe = (Resolve-Path -LiteralPath '.\qbrain.exe').ProviderPath
$db = (Resolve-Path -LiteralPath "$env:LOCALAPPDATA\Qbrain\brains\my-brain\brain.db").ProviderPath
$backupParent = (Resolve-Path -LiteralPath 'D:\QbrainBackups').ProviderPath
$restoreParent = (Resolve-Path -LiteralPath 'D:\QbrainRecovered').ProviderPath
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
$backup = Join-Path $backupParent ('snapshot-' + $stamp)
$receiptPath = Join-Path $backupParent ('snapshot-' + $stamp + '.receipt.json')
$restore = Join-Path $restoreParent ('restored-' + $stamp)
if ((Test-Path -LiteralPath $backup) -or (Test-Path -LiteralPath $receiptPath) -or (Test-Path -LiteralPath $restore)) {
    throw 'Choose new output names; do not overwrite existing data.'
}

# 1. 创建一致性快照。回执放在快照目录之外，不能往快照内加第三个文件。
$raw = & $exe backup create --database $db --output $backup
if ($LASTEXITCODE -ne 0) { throw ($raw -join "`n") }
$receipt = ($raw -join "`n") | ConvertFrom-Json
if ($receipt.result -cne 'CREATED') { throw 'Unexpected backup receipt.' }
$pin = [string]$receipt.manifest_sha256
if ($pin -cnotmatch '^[0-9a-f]{64}$') { throw 'Invalid manifest identity.' }
# 此回执不含原始内容或路径，ASCII JSON 可跨 PowerShell 版本读取。
$raw | Set-Content -LiteralPath $receiptPath -Encoding Ascii

# 2. 使用创建时另存的可信摘要校验。
& $exe backup verify --backup $backup --expect-sha256 $pin
if ($LASTEXITCODE -ne 0) { throw 'Backup verification failed; do not restore.' }

# 3. 只恢复到新目录，不替换当前使用中的 brain.db。
& $exe backup restore --backup $backup --expect-sha256 $pin --output $restore
if ($LASTEXITCODE -ne 0) { throw 'Restore failed; preserve the original backup and inspect the new directory.' }
Get-Content -Raw -LiteralPath (Join-Path $restore 'RESTORE.json') | ConvertFrom-Json
```

日后恢复时，从创建时可信保存的回执读取 `manifest_sha256`。不要在恢复前仅对来源
不明的 `manifest.json` 重新算一个摘要，然后把它当成“可信摘要”：攻击者若同时替换
数据和清单，这样做只能证明它们自洽。摘要应与备份分开妥善保存；摘要不是签名，
不能证明是谁生成文件，也不能保护被同时篡改的所有副本。

上述 PowerShell 组合示例是使用说明。实际验收覆盖原生命令与 Python 驱动的 Windows
子进程，不应把这段手工操作文字冒称在用户本机执行过的脚本。

## 一致性与文件格式

`create` 以 SQLite 只读连接建立固定读事务，再使用 online backup API 复制，
不会直接复制一个正在变动的 `brain.db`。已提交但尚在 WAL 中的数据会纳入快照，
未提交事务排除。快照对应固定读事务观察到的提交状态，不必等于命令结束时最新状态。

WAL 模式允许备份期间其他连接继续提交；回滚日志模式下，读事务可能使写入方等待。
这不是零影响备份。升级前关闭相关应用通常能简化操作；不要删除 WAL/SHM 文件或
强制 checkpoint 来“帮助”备份。程序不主动迁移或更新源数据库业务数据，但 SQLite
本身可能维护共享内存等辅助状态，不能承诺所有辅助文件元数据绝对不变。

备份目录恰有两个文件：`snapshot.sqlite3` 和 `manifest.json`。快照转换为独立的
回滚日志格式，不需要原库的 WAL/SHM。清单绑定准确大小、数据 SHA256、结构版本和
明确范围，最后写入。`verify` 检查外部摘要、两文件清单、规范化 JSON、数据摘要、
SQLite 完整性和外键，再复查输入。多余的日志、备注、隐藏文件也会被严格清单拒绝。

恢复结果为新目录中的 `brain.db` 和 `RESTORE.json`。数据文件在恢复时与已核验快照
逐字节一致；后续用 Qbrain 打开后，正常日志模式或迁移可能改变文件，因此不要将
打开后的文件字节差异直接判为恢复失败。把恢复库用于生产前，应另外确认应用语义、
配置及数据库之外的资料。命令不会执行这次切换，也不会修改默认脑库注册信息。

## 失败和验证边界

数据库上限为 268,435,456 字节（256 MiB），清单上限 8,192 字节。
数据库会整体读入内存进行摘要与字节复核，峰值内存可能明显高于单个数据库大小；
不是大库流式灾备。超过范围会拒绝，不截断。当前粗粒度识别要求存在
`schema_version`、`sources`、`pages` 表，结构版本为 1–13，不进行源库迁移。
该检查不能认证任意文件是真实 Qbrain，也不是对所有历史版本完整语义的承诺。

SQLite `integrity_check` 与 `foreign_key_check` 通过不代表所有业务约束、FTS 内容同步、
外部附件和应用语义都得到证明。回执明确保留 `application_semantics_verified=false`。
本轮测试额外检查了真实合成事实/回执和全文检索，但不能替代实际恢复后的业务验收。

`--timeout-ms` 范围 100–120000，默认 10000；限制 SQLite 等锁和进度等待。
文件系统调用、摘要计算、同步和清理不是可硬中断的实时上限。超时不要通过盲目重复
覆盖目标来处理；先查找锁与磁盘问题，再选新目录重新执行。

普通文件、路径及所有父层的链接/reparse 检查和独占创建减少误写风险；本地恶意
并发替换路径、操作系统故障、存储硬件错误或不可信可执行文件不属于安全沙箱保证。
Windows 不接受 UNC、设备路径和备用数据流；使用本地正常磁盘路径。

磁盘满、拒绝访问、断电或进程中断可能留下部分新目录。程序不报告成功，不自动
删除这些目录，也不会放宽“目标不存在”的要求。最终应依据成功回执、外部可信摘要
与完整 `verify`，不能仅凭某个清单文件存在判断操作完成或数据已持久化到可靠介质。
没有目录级断电原子提交或硬件持久性认证。

SQLite 官方设计参考（2026-09-27复核）：
https://www.sqlite.org/backup.html
https://www.sqlite.org/c3ref/backup_finish.html
https://www.sqlite.org/pragma.html

本模块不改变旧 N48K ZIP、发布标签、MCP 权限或 Issue40 状态；真实客户端记忆消费、
模型质量、PG 对等与签名仍为其他验收事项。
