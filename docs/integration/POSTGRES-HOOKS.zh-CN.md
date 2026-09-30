# N48R：PostgreSQL Hook 接入与联合记忆快照

## 作用和边界

N48R 补齐已存在的 Hook 接口在 PostgreSQL 下的连接与读取流程。它不是新的
模型服务，也不代表已经登录真实 Claude/Codex 并证明模型使用了记忆。
SQLite 仍默认；只有 Hook 进程继承了非空 `QBRAIN_PG_DSN` 才使用 PostgreSQL。

本模块只连接已经初始化的 PostgreSQL：核心 schema 版本 13、public、UTF8，
且核心表实际解析为预期的 public 表。Hook 不调用核心初始化或迁移；连接失败、
空库、未知版本和不合要求的 schema 返回空 JSON，不读取同名本地 SQLite 作为回退。
这避免“远端连接失败，却向客户端注入了另一份本地脑库”的错误。

同一 DSN 更换 `--brain` 标签不是独立 PostgreSQL 租户，source 不是 RLS。
数据库所有者和 SQL 管理员仍需可信；不同租户应由实际数据库访问控制隔离。

## 联合读取和撤回

启用 `fact_recall` 后，结构化事实和普通会话记忆在同一个模块拥有的
REPEATABLE READ READ ONLY 快照里读取。其他连接在读取期间提交遗忘或撤回时，
本次只看到一个一致版本，下次读取看到新状态；不是把前后两个版本拼起来。
普通 memory 接口没有因此开放调用方事务；Hook 也不能借用任意已有、失败或写事务。

事实保留完整用户证据与明确声明的矛盾，不推断赢家或置信度。被事实引用或同原话的
普通记忆不会绕过事实通道重返输出，因此撤回事实不会通过普通会话记忆“复活”。
只有整个输出对象能放入预算时才返回，不能截断成半段 JSON 或半个矛盾组。
联合读取结束后，才进入另行授权的采集、本地提取与事实提升。

普通会话记忆的会话内去重包含有效服务器、数据库和角色的描述摘要。相同会话和
相同记忆 ID 在另一 PostgreSQL 数据库中不会被上一数据库的去重状态误屏蔽。
SessionStart、PreCompact、SessionEnd 按既有规则重置当前作用域的去重状态。
这不是对事实组的永久屏蔽，也不是对数据库重建后身份的强加密认证。

## Windows 使用准备

程序是未签名的 Windows x64 开发候选，需要匹配的 Visual C++ x64 运行库。
PostgreSQL 构建还需要可信的 libpq 及其依赖；小工具包不捆绑数据库服务或这些依赖，
不要从不明 DLL 下载站补齐文件。无需自行编译，但不是免依赖的一键安装包。

沿用已有项目级安装方式和 `scripts/Install-QbrainMemory.ps1`／
`scripts/Invoke-QbrainJson.ps1`。安装脚本本身会显式执行初始化，不能把“Hook 不初始化”
误解为“运行安装脚本也绝不初始化”。本次没有在用户电脑执行安装、升级或连接真实脑库。
已经安装的宿主必须真正继承 PostgreSQL 连接环境；只在另一个 PowerShell 窗口设置变量，
不会改变已经启动的宿主进程。连接信息应留在授权的本地环境或凭据管理中，不放入仓库、
聊天或 Hook 诊断文件。变更实际连接前应确认备份和数据库身份。

配置示例（故意禁用；不包含连接串）：

```json
{
  "version": 1,
  "enabled": false,
  "host": "claude",
  "project_root": "C:\\Projects\\Example",
  "brain_id": "example",
  "source_id": "default",
  "capture": false,
  "extraction": "local",
  "recall_bytes": 4096,
  "max_items": 8,
  "fact_recall": true,
  "fact_promotion": false
}
```

`host` 必须对应实际适配器（claude 或 codex）；项目路径与调用工作目录必须相符。
采集需安装配置 `capture` 和共享 `memory.writeback` 同时允许。
`fact_promotion` 另需显式开启且只允许本地采集/提取路径；外部模型许可和 MCP 写许可
不会由此自动获得。默认不调用付费模型。

## 隔离自测

工具包包含 `review_pg_hook_closeout.py`。有 Python 3.10+ 时可在解压目录的
PowerShell 执行下列 SQLite 自测；它使用独立临时 HOME，不连接真实脑库或 PostgreSQL，
不需要宿主登录，不会安装 Hook。程序本身的 libpq/VC 依赖仍应先具备。

```powershell
$report = Join-Path $env:TEMP ("qbrain-hook-check-" + [guid]::NewGuid().ToString("N"))
python .\review_pg_hook_closeout.py --binary .\qbrain.exe --output $report
if ($LASTEXITCODE -ne 0) { throw "Hook 自测失败；保留输出供检查：$report" }
Get-Content -LiteralPath (Join-Path $report "RESULT.json") -Encoding UTF8
```

`--postgres` 是开发 CI 的专用测试入口，需要专门创建的固定名称临时数据库和显式授权。
不要把生产数据库改成测试库名称来运行它。Python 是可选自测工具，不是程序常驻依赖。

## 异常与回退

Hook 输出 `{}` 可能表示没有结果、未获许可、输入无效或连接/读取失败，不能只凭退出码
判定召回成功。使用已有元数据诊断检查阶段，不把诊断中的返回记忆数量当作模型消费证明。
日志不记录用户原话或 DSN；跨库去重的描述是内部摘要输入，不是诊断输出。

Hook PG 连接的 statement_timeout 为 2500ms；这不是对 DNS、网络握手、文件锁或所有 OS I/O
的全流程硬截止承诺。现有宿主进程监督未改写，Issue #40 不因本模块关闭。
需要停用时沿用已有项目级禁用/卸载方式，不删除或降级数据库 schema；本模块没有新增
自动迁移或清表操作。旧发行 ZIP 与公开 Release 没有被替换。

审核与固定版本见 [N48R-HARD-AUDIT.md](../nodes/N48R-HARD-AUDIT.md)，
机器可读结果见 [RESULT.json](../nodes/n48r-evidence/RESULT.json)。
