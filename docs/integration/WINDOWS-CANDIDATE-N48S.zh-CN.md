# N48S Windows 统一集成候选包

本包把截至 N48R 的同一份产品源码与配套安装、评测、备份和 PostgreSQL 说明集中交付。
固定产品源码：e0a27f829d970c24ed8c566023ada0911c0042b3。
这是未签名工程候选，不是稳定版，不代表整个 qbrain 已结项。

## 使用前先核验

只有配套的外部 ACCEPTANCE.json 表明 PASS_BOUNDED_WINDOWS_CANDIDATE，
并且其 package_sha256 与下载 ZIP 一致时，才能把此包视为已完成限定验收。
包内 MANIFEST.json 的 BUILT_NOT_YET_ACCEPTED 是构建时的真实状态，测试结束后不重写 ZIP。

```powershell
(Get-FileHash .\qbrain-windows-x64-n48s-candidate.zip -Algorithm SHA256).Hash.ToLowerInvariant()
```

对照随交付记录提供的完整摘要后，解压到新目录，保留旧程序、配置和数据备份。
不要覆盖正在使用的程序目录。不要先删除 brain.db、WAL 或 SHM 来处理安装错误。

## 一份程序，明确的两种存储路径

默认 SQLite 路径不要求 PostgreSQL 服务、Python 或 Docker/WSL。
此构建的实际 PE 直接导入必须只有允许的 Windows 系统库；libpq.dll 只能是延迟导入。
验收还会在 PATH 只保留 Windows System32 的环境下执行 SQLite 初始化、计价、备份和体检。
这不代表任意 Windows 镜像、全部动态加载行为或所有系统组件都经过穷尽测试。

显式设置 QBRAIN_PG_DSN 后才选择 PostgreSQL。PG 功能仍需可信的数据库服务器、
兼容的 libpq 及其全部依赖；本包不含这些第三方 DLL。
libpq 本身可能需要 Visual C++ 运行库，因此“SQLite 不依赖第三方启动 DLL”
不等于“PostgreSQL 免依赖”。不要从不明网站逐个下载 DLL。
先配置完整可信的 PG 客户端环境，再启动宿主。连接字符串和密码不要上传到聊天或仓库。
更换 --brain 标签不等于建立独立 PG 租户，source 也不是数据库行级权限。

## 先做不会写脑库的离线计价示例

在解压目录的 cmd.exe 中：

```bat
qbrain.exe cost compare < examples\cost\compare-basic.json
echo %ERRORLEVEL%
```

预期退出 0，候选减基准为 -0.000050000000，精确比例为 -5/12。
这是合成费用，不是供应商报价或效果证明。PowerShell 不支持上述同样的输入重定向语法；
PowerShell 调用 JSON 时使用包内 scripts/Invoke-QbrainJson.ps1。

## 安装、升级与停用

项目级接入沿用 scripts/Install-QbrainMemory.ps1；参数和恢复规则见
docs/integration/INSTALLER-RECOVERY.zh-CN.md、POSTGRES-HOOKS.zh-CN.md。
采集开关、共享写回策略、事实提升和外部模型外发是独立许可；本包不自动开启它们。
脚本可能按明确的安装操作初始化目标库；Hook 的“只连接已有 PG 库”不约束显式安装初始化。
执行前明确核对 -ProjectPath、-BrainId 和当前进程是否设置 QBRAIN_PG_DSN。
不要把该说明理解为本轮已经安装到用户电脑或已登录真实 Claude/Codex。

升级前备份。SQLite 原生 backup create/verify/restore 与 database check 的完整规则见
docs/integration/SQLITE-BACKUP.zh-CN.md 和 SQLITE-CHECK.zh-CN.md。
备份是明文数据库，不包含库外附件、宿主配置或全局注册文件，不是整个环境灾备。
恢复只写新目录，不自动替换活动脑库。PG 备份由服务器管理员按 PG 原生流程执行。

## 包内功能与可选评测

原生程序包括会话记忆、结构化事实和显式使用回执、分层上下文、Hook/MCP、
SQLite 一致性备份与全文索引体检，以及费用计算和供应商响应导入。
PG 会话、上下文、事实/回执和 Hook 均在此固定产品版本中，不必再拼接四个模块工具包。

tools/acceptance 下的 Python 是可选离线评测工具，不是常驻服务。
model_evaluation.py 联合评估同一次执行的逐题质量与主请求费用；
model_cost.py 从已有执行回执生成费用账本；完整格式见 MODEL-QUALITY-COST.zh-CN.md。
价格、计划、运行记录和评分键由操作者明确提供。不要把真实执行数据提交到公开仓库。
模型 execute 仍有单独授权要求，包的验收使用合成回环响应，不发起付费请求。
主请求计价不等于全流程费用统计。

## 验收边界

此包必须通过同一 EXE 的原生60组、解压后55步回归、备份/体检、真实PG Hook测试、
两版PowerShell安装恢复，以及旧版已有有效/撤销回执的升级、回退和卸载快照核对。
数字是工程测试覆盖，不等于模型语义正确率。只看某个子步骤绿灯不足以证明整个包验收。

真实客户端后续会话是否消费记忆、代表性模型质量与全流程费用、
尚未闭合的完整需求、签名稳定版和 Issue40 仍有独立门槛。
本包不修改旧 N47X Release 或历史固定 ZIP；源码、构建工具和实际程序摘要分别记录。
