# N48P：PostgreSQL 分层上下文与摘要缓存

2026-09-29。固定受测源码 `136a4828ec31eeb5d870b3a3814d5b5c533783d6`。
实际合并身份见 PR58；不是全项目 PostgreSQL 对等或真实客户端消费验收。

## 已实现

现有 `context list/read/summary` 和 MCP `context_read/context_write` 可使用 PostgreSQL。
SQLite 仍默认，只有显式设置 QBRAIN_PG_DSN 才选择 PG，不自动迁移 SQLite 数据。
`memories/`、`resources/`、`skills/` 是同一 source 下的逻辑命名空间；不混入其他
source 或命名空间的页面。这里读取的是页面原文／预览，不等于 fact_store 的结构化事实。

L0 是短预览，L1 是更长的提取式预览或已有模型摘要；L2 是单页原文的 UTF-8 字节分页。
目录只能读 L0/L1；读取不调用模型，也不初始化可选缓存表。完整应用启动仍可能
初始化核心库结构、读取本地配置或创建本地目录，不能把它描述为文件系统无操作。

## Windows 前提

工具包包含固定受测的 Windows x64 EXE，不需要自行编译，也不需要 Python 常驻服务、
Docker 或 WSL。EXE 未签名，是开发候选，不是稳定版安装器。它需要相应的 Visual C++
x64 运行库；PG 路径另需可信 PostgreSQL 服务、兼容 libpq 及其依赖，包内不捆绑这些依赖。
请从可信原生安装取得依赖，不从不明网站逐个下载 DLL。

该 EXE SHA256：
`318ac7c3f69f7dd440a5d3946204bf311abf416403b0075525e39762ba8e264b`。
旧 N48K、N48O 固定包和公开发行包不被替换，不能拿旧 EXE 验证新增 PG 功能。

## 先运行不连接 PostgreSQL 的合成示例

下列 PowerShell 命令只适用于一个**未使用过的测试 brain 名称**。先确认当前进程没有
QBRAIN_PG_DSN，避免把合成数据写入共享服务器。示例写入本地测试库，不修改默认 brain
选择，不开启模型外发。重复运行 put 会更新同一测试页面，因此不要替换成真实页面名。

```powershell
$ErrorActionPreference = 'Stop'
if (-not [string]::IsNullOrWhiteSpace($env:QBRAIN_PG_DSN)) {
    throw '请在未设置 QBRAIN_PG_DSN 的独立 PowerShell 窗口运行此 SQLite 合成示例。'
}
$brain = 'n48p-context-demo-new'
.\qbrain.exe init --no-default --brain $brain
if ($LASTEXITCODE -ne 0) { throw 'init failed' }
.\qbrain.exe config set embed.auto false --local --brain $brain
if ($LASTEXITCODE -ne 0) { throw 'config failed' }
.\qbrain.exe put --slug docs/n48p-demo --title N48P-Synthetic --file .\samples\pg-context.synthetic.txt --json --brain $brain
if ($LASTEXITCODE -ne 0) { throw 'put failed' }
.\qbrain.exe context read --source default --uri qbrain://default/resources/docs/ --layer L1 --brain $brain
if ($LASTEXITCODE -ne 0) { throw 'read failed' }
.\qbrain.exe context summary --source default --uri qbrain://default/resources/docs/ --method extractive --brain $brain
if ($LASTEXITCODE -ne 0) { throw 'summary failed' }
.\qbrain.exe context read --source default --uri qbrain://default/resources/docs/n48p-demo --layer L2 --max-bytes 512 --brain $brain
if ($LASTEXITCODE -ne 0) { throw 'raw read failed' }
```

对应原生命令和样本已在隔离的 Linux 环境执行；上述 PowerShell 脚本没有在用户本机
运行。实际 Windows CLI/MCP 以及 PG 的验收来自固定源码 CI，不能混作本机执行。
在源码目录运行时，EXE 为 build/cl/qbrain.exe，样本在 examples/context/ 下。

## 使用已授权的 PostgreSQL 上下文

管理员应先备份并为测试建立独立的 UTF8 数据库／角色，再安全配置进程的 QBRAIN_PG_DSN。
不要在文档、仓库或聊天中粘贴真实连接密码。连接远程 PG 本身就是把数据传给该服务器。

```powershell
.\qbrain.exe context list --source default --brain pg-demo
.\qbrain.exe context read --source default --uri qbrain://default/resources/docs/ --layer L1 --max-bytes 2048 --brain pg-demo
.\qbrain.exe context summary --source default --uri qbrain://default/resources/docs/ --method extractive --brain pg-demo
```

URI 必须属于明确的 source；实际页面应已经存在于目标库。summary 是显式写入缓存的
操作，不是只读。首次合法发布原子创建 context_module-v1、context_cache、失效函数和
四个触发器；没有授权或证据变化时不抢先建立这些可选对象。不会替换未知用户对象。
PG 使用 public 模式，拒绝不兼容布局、异常表解析或已有调用方事务。

**同一 DSN 下改 --brain 标签不是数据库租户隔离；source 也不是 PG 行级安全。**
不同主体需要硬隔离时，使用分别授权的数据库和角色。本模块未实现 RLS 或完整 DLP。
CLI 数据库访问、TLS、角色权限和备份由操作者负责。MCP 保留写默认拒绝与允许来源检查。

## 分页、版本和大小

L2 响应中的 offset/next_offset 是 UTF-8 **字节位置**，不是字符、token 或页号。
后续请求应同时传入上一响应的 next_offset 与 revision。正文修改后，旧 revision
返回 stale_or_invalid_cursor；不能把旧分页片段拼到新原文。不得在一个 UTF-8 标量的
中间开始读取。末页 next_offset=null。分页是在每次请求的快照上绑定版本，不持有跨
请求的数据库事务。L2 原文不被模型改写，CRLF、中文和 emoji 均保留。

序列化 JSON 预算为 512–32768 字节，默认 8192；它不保证具体模型 token 数。
单页原文最多 16 MiB。目录最多读取前 256 页，按 slug 的 C 排序及 id 排序；这批正文
累计上限 16 MiB，超限拒绝，超量正文不会先作为 libpq 结果传回。目录结果可能因为
页数、预览或响应预算而截断；不能把预览当成完整正文或完整知识库。

## 缓存、并发和许可

cache_status=missing 表示没有对应缓存；fresh 表示当前有效缓存；stale 使用当前正文
重新生成提取式预览。页面 INSERT/UPDATE/DELETE 以及 PG TRUNCATE 都清除派生正文和
引用并置脏；页面移动来源时两边失效，软删除和命名空间变化也失效，事务回滚还原。
本模块不尝试在后台自动修复用户改写／禁用的触发器、函数或未知表布局，而是拒绝。

PG 读取使用 REPEATABLE READ READ ONLY 单事务快照。summary 先取证据再结束读取事务；
模型回调期间不持有该事务。发布时按 sources/pages/config 的固定顺序短暂加锁，重新
核对来源、正文版本、有效表解析和外发许可；迟到结果不能覆盖已变化的证据。
写事务局部锁等待预算为 2500 ms，不修改调用方配置，也不自动重试付费模型请求。
这不是高吞吐、任意负载或恶意数据库所有者的安全保证。

默认 extractive 不调用模型。model 需要现有 context.external_summary=allow 与可用
模型配置，MCP 还要写权限；工具包不会自动开启这些许可。模型摘要仍标记为不可信
派生文本，原文才是依据。合成回调测试不能证明真实模型质量或所有敏感信息都被识别。

CLI 成功通常退出 0，契约／访问错误退出 1，启动／连接等错误可能为 2；应同时查看
结构化错误码。context_transaction_active 不会替调用方提交事务；context_pg_schema_context
表示表解析／当前模式／编码或复制角色不受支持。context_schema_incomplete 表示失效
组件异常；不要删表、改版本号或放宽权限来隐藏报错。

## 版本与剩余范围

N48P 只补齐分层上下文与摘要缓存的 PG 路径，没有完成 fact_store、Hook、所有 PG 对等、
真实客户端语义消费、真实模型质量／全流程费用、签名或稳定版。Issue40 独立保留。
SQLite 备份／文件体检不能接收 PG DSN；服务器灾备需使用管理员的 PG 备份方案。
回退本模块不自动删除已存在的缓存表或用户数据。

[源码审核](../nodes/N48P-HARD-AUDIT.md) · [验收索引](../nodes/n48p-evidence/RESULT.json)
