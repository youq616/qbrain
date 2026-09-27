# N48N：SQLite 深度体检与全文索引诊断

## 适用范围

本工具检查明确指定的本地 Qbrain SQLite 数据库。它先建立只读事务，再通过 SQLite
online backup 取得私有内存快照；深度检查在副本执行。它不迁移、修复或重建原库，
不选择默认脑库，不读取模型配置，不发送模型请求，也不新增 MCP 写入权限。

程序支持本版本识别的 v13 库结构，数据库上限 **256 MiB**，覆盖该数据库内全部
source。它不是完整业务验收、来源认证、PG 体检、恶意数据库安全沙箱或灾备工具。
读取旧版或未来版本时不会自动升级；识别范围之外的结构不能得到全部通过。

**只读不等于文件系统完全不变。** SQLite 可以创建空 WAL、SHM 或更新共享内存记账；
已有业务数据不会被这个命令修复或改写。内存副本包含完整明文数据，也可能被操作系统
换页。必须在有授权的、可信本地目录里运行，不能把它当成检查任意恶意文件的沙箱。

## Windows 使用

使用新的 N48N 工具包，解压到独立目录，在该目录打开 PowerShell。无需 Python、
Docker 或 WSL。程序未签名，是经过源码验收的开发候选，不是安装器或稳定版。
旧 N48K/N48M 固定 ZIP 和公开 N47X 发行包不被替换；旧程序不包含这个体检入口。
不要用程序内部通用版本字符串识别本次构建，应核对下面的 SHA256。

受测源码：`b6d0e8002cefffbf94d21144080a66a5a198f238`。
Windows x64 `qbrain.exe` SHA256：

```text
aa182648bf19e326e2e957acfb636dcd8fe2895aab83aea26c2e91de5fbaa0b4
```

```powershell
(Get-FileHash .\qbrain.exe -Algorithm SHA256).Hash.ToLowerInvariant()
```

工具包附带两个原生 Windows CI 生成的**合成数据库样本**，不是用户数据。
先检查健康样本，再检查故意制造的索引失配样本：

```powershell
.\qbrain.exe database check --database ".\samples\healthy.db"
$LASTEXITCODE

.\qbrain.exe database check --database ".\samples\stale-index.db"
$LASTEXITCODE
```

第一条应为 `CHECK_PASSED`、退出码 0。第二条应为 `CHECK_FAILED`、退出码 1，
其中 `sqlite_integrity` 仍为 PASS、`fts_content` 为 FAIL。这是预期反例，
用来证明普通结构检查通过不代表全文检索结果没有失配。不要删除失败项使样本变绿。
工具包 `samples/*.expected.json` 保存实际 Windows 输出以供对照。

检查自己的数据库时，明确替换路径，不要直接复制示例路径当成真实库位置：

```powershell
.\qbrain.exe database check --database "D:\YourAuthorizedBrain\brain.db" --timeout-ms 10000
$LASTEXITCODE
```

支持带空格和中文的普通本地路径。不接受重复/未知选项、`..` 路径段、SQLite URI、
UNC、Windows 备用数据流，以及源路径或现有 WAL/SHM/journal 的链接和异常文件类型。
相对路径以当前工作目录为基准；不自动猜测或打开默认脑库。不要为了绕过报错而删除
活动库的 WAL/SHM/journal，也不要随意移动正在使用的数据库文件。

## 七项结果

| 标识 | 检查内容 | 边界 |
| --- | --- | --- |
| `sqlite_integrity` | SQLite 自身结构完整性 | 不等于外部正文与 FTS 索引一致 |
| `foreign_keys` | 数据库实际声明的外键 | 未声明的业务关系须另查 |
| `core_inventory` | 本版本已知的 v13 表、部分字段和索引名称 | 不验证所有字段类型、约束、索引列或完整业务语义 |
| `page_relations` | 页面来源、三个页面子表引用及同 source/slug 重复 | 不覆盖全部业务不变量 |
| `fts_definition` | `pages_fts` 是否符合规范声明 | 非规范但等效的自定义 SQL 也可能需人工复核 |
| `fts_triggers` | 三个标准索引维护触发器 | 触发器正确不代表旧索引内容已经正确 |
| `fts_content` | FTS 索引与当前正文的一致性 | 使用私有内存副本上的 FTS5 rank=1 检查 |

SQL 比较保留词法边界和字符串字面量；允许注释、空白和未引用标识的大小写变化，
不通过删除空格把不同字符串或标识混成同一个。全文索引的一致性是分词结果的一致性，
不是原始字符串逐字节相同；例如改变大小写但保持同样分词，不应被误报为索引损坏。

每项状态为 `PASS`、`FAIL` 或 `NOT_RUN`。依赖条件不满足时明确标记未运行，
不能当作通过。报告不输出源路径、正文或原始 SQLite 错误文本，只给固定问题码。

| 总结果 | 退出码 | 应如何处理 |
| --- | --- | --- |
| `CHECK_PASSED` | 0 | 七项限定检查全部通过；不是完整业务验收或未来状态保证 |
| `CHECK_FAILED` | 1 | 已查出结构、关联或索引问题；保留报告和原数据，不自动修复 |
| `ERROR` | 2 | 输入、权限、锁等待、超时或其他操作失败，不能据此判断数据库健康 |

超时默认 10000 ms，可设 100–120000 ms。期限约束 SQLite 忙等/执行检查，不能硬实时
打断所有操作系统 I/O、内存分配或调度。超时不是结构损坏；可在负载较低、没有长事务
的时段重新检查，或在允许范围内给出明确预算。数据库大小上限不等于进程峰值 RAM 上限。

## 发现问题后的安全处理

本命令没有 `repair`、`rebuild` 或自动恢复选项。先保存报告、确认正在检查的库及其
版本，再用已验证的[备份流程](SQLITE-BACKUP.zh-CN.md)保护数据。要调查修复行为时，
优先在新目录的恢复副本上验证，不能把“自动修复后不报错”当作原始数据从未有问题。
备份模块的结构校验也不等于这次新增的 FTS 内容检查；恢复副本可再次运行本命令。

并发写入时只检查一个已提交事务快照，不包括未提交数据或后续提交。检查完成后，
新的写入仍可能改变健康状态；诊断不会锁定数据库为永久健康。链接拒绝检查也不是
抵御恶意并发路径替换的完整安全边界。

## 构建、证据与版本边界

Windows 构建沿用仓库 `scripts/build-tests-cl.ps1`，完整原生程序和原 60 组测试不变。
新直接测试可用 `cmake -S tests/sqlite_check -B build/check` 编译，并用 CTest 执行；
完整原生 CI 另跑原备份与 55 步回归。Python 只用于离线测试/证据审核，不是产品运行依赖。

[源码审核](../nodes/N48N-HARD-AUDIT.md) ·
[精确结果](../nodes/n48n-evidence/RESULT.json) ·
[当前状态](../../CURRENT-STATUS.md)。实际合并身份见 PR55 和交付记录。
真实客户端记忆消费、真实模型质量与费用、PG、签名、稳定版和 Issue40 仍独立保留。
