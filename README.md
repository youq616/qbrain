# Qbrain

Windows 原生 C++20 / PowerShell Agent 记忆与知识库，默认 SQLite + FTS5。
不要求 Docker、WSL 或 Python 服务。由 Lordakee/qbrain 的 MIT 代码继续开发；
gbrain / OpenViking 是设计参考，不代表完整功能等价。

## 当前开发预览：N47D

[仓库 Release：hook-fact-preview-5275045c](https://github.com/youq616/qbrain/releases/tag/hook-fact-preview-5275045c)
选择 `qbrain-windows-x64-hook-facts.zip`，完整解压。SHA256：
`89918f2ed6964b4051d4542b7cd2358406423b6f3111db202e92e89e043086e8`。
这是未签名开发预览，原CI测试字节、没有重新打包。不是全项目完成的正式发行。
实际源码 `5275045c4790b802b620ba0af52ec6248cd587d5`；
[PR #19](https://github.com/youq616/qbrain/pull/19)已合并。
以MANIFEST、完整源码SHA和外部摘要识别版本，不用历史dist或旧固定哈希工具替代。

[当前状态](CURRENT-STATUS.md) · [阶段复核](docs/nodes/N47D-HARD-AUDIT.md) ·
[测试摘要](docs/nodes/n47d-evidence/SUMMARY.json) · [发布记录](docs/nodes/n47d-evidence/RELEASE.json)

## 新增：显式开启 Hook 事实召回

安装器 `-EnableFactRecall` 单独开启该项目的事实Hook，默认关闭，独立于本地采集。
开启后，新会话可带入近期active事实；用户提交问题时按现有字面词规则召回匹配事实。
每个事实及有效直接冲突对方完整输出，事实组优先，普通记忆用同一个JSON响应预算的
剩余空间。放不下不会拆成半组，同源事实绑定项或完全相同原话不能从普通记忆绕回。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Install-QbrainMemory.ps1 -HostName Claude -ProjectPath "D:\Projects\MyProject" -Binary ".\qbrain.exe" -EnableFactRecall
```

仅需要普通记忆则不传这个开关；需要该项目本地采集时另加 `-EnableCapture`。
事实开关不自动创建事实、判断真假、扩展MCP写授权或开启Qbrain外部提取/摘要。
`Status`显示开关状态，重装不传开关即关闭；卸载继续保留脑库与备份。
[详细语义和安装](docs/integration/HOOK-FACT-RECALL.zh-CN.md)。

**Hook上下文交给用户已授权客户端，客户端可能发送至其模型。** 没有额外Qbrain
模型请求不表示没有客户端外发。不修改登录、全局Agent设置或绕过信任要求。

## 证据、预算与遗忘边界

事实与普通记忆共享一个SQLite读快照，采集在读取后执行；事实每次重新核验，避免
会话去重掩盖revision或支持证据变化。不把事实原话或查询词写进trace/去重状态。
recall_bytes限制每次完整序列化Hook JSON，不是整段会话Token预算；空+truncated表示
结果不完整。默认开关关闭时保留原Hook行为。数量预算不等于SQL扫描或硬实时保证。

逐事件forget不全局删除所有同句独立记录；另一个未遗忘副本可能仍作普通记忆返回。
撤回事实尚存在时，其绑定项/完全相同原话仍被普通通道过滤。客户端旧上下文和备份
不是安全擦除目标。原文哈希是本地一致性检查，不是数字签名或完整多用户权限体系。

## 已有能力

N47A提供有完整原文证据的事实创建、附加支持、撤回、替代和显式矛盾关系；首次
明确事实写入先备份并初始化独立可选表，不替换历史facts。N47D没有新迁移。
N47B成对查看冲突；N47C按查询召回并保留直接反证，无自动语义推断或真假赢家。
[事实](docs/integration/EVIDENCE-FACTS.zh-CN.md) ·
[冲突](docs/integration/CONFLICT-INSPECTION.zh-CN.md) ·
[主动召回](docs/integration/FACT-RECALL.zh-CN.md)。

原会话归档/记忆、来源隔离、采集开关、重试去重、遗忘联动、项目Hook与可撤销安装；
L0/L1摘录、单独许可的可选摘要、L2分页、缓存失效、六工具MCP；CJK连续子串搜索，
精确有界向量候选、Embedding模型标签隔离、批量队列和过期结果拒绝保持。
HTTP共享不可变会话与逐请求状态保持，系统代理设置改变后需重启进程。

## 验证与尚未验收部分

原生34862423429/34862423691必需任务通过：Windows52注册组；新组合单元在两Windows
版本和portable各13场景229断言；真实EXE事件夹具52项72命令；PS5.1/7事实开关安装
各33项。旧事实/冲突/召回/HTTP/队列/CJK/记忆/Hook/双PowerShell门槛保留；真实PG DSN
仍明确跳过。187项原始源码/日志/交付回读，Linux Clang ASan/UBSan与独立组合对照、
故意破坏副本和82项报告门槛补查通过。阶段是单独工程自审，不是第三方/子代理审核。

**事件夹具不是真实已登录Claude/Codex会话。** 新版实际模型消费、遗忘后新会话和项目
隔离需按[本机任务](docs/integration/N47D-LOCAL-ACCEPTANCE.zh-CN.md)完成三个隔离会话。
不需要编译器、GitHub写凭据或重复源码审核；现有Codex认证问题不由本轮修复。

自动语义提取/冲突判断、衰减画像、PG对等、完整ACL/DLP、真实模型质量费用、正式签名
与整个融合项目完成均未声明。不存在已知本阶段P0/P1不等于软件绝无潜在问题。

## 从源码构建、数据与交接

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-cl.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-tests-cl.ps1 -SkipProductionBuild
```

源码构建需要MSVC；只有同轮生产构建成功且源码未变才跳过重复构建。运行预编译包
不要求编译器，Python是CI/验收依赖而非产品服务。升级前备份已有脑库，完整解压同包，
默认数据为 `%LOCALAPPDATA%\Qbrain\`；不上传真实聊天、数据库或密钥。
[完整安装说明](docs/integration/QUICKSTART.zh-CN.md) · [接入细则](docs/integration/WINDOWS-MEMORY.md)。
本机任务只给一个完整提示词，文件先放仓库并提供固定地址、摘要及用法，遵循
[交接规则](LOCAL-AGENT-HANDOFF.md)，不让本机并行重写同一代码。

## 历史与许可

[N47C](docs/nodes/N47C-HARD-AUDIT.md) · [N47B](docs/nodes/N47B-HARD-AUDIT.md) ·
[N47A](docs/nodes/N47A-HARD-AUDIT.md) · [N46F](docs/nodes/N46F-HARD-AUDIT.md)。
[Issue #2](https://github.com/youq616/qbrain/issues/2)保持总路线跟踪；历史失败记录保留。
MIT；保留[LICENSE](LICENSE)及[第三方许可](THIRD-PARTY-NOTICES.md)。
