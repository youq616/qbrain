# Qbrain

Windows 原生 C++20 / PowerShell Agent 记忆与知识库，默认 SQLite + FTS5。
不要求 Docker、WSL 或 Python 服务。由 `Lordakee/qbrain` 的 MIT 代码继续开发；
gbrain / OpenViking 是设计参考，不是完整功能等价声明。

## 当前已发布开发版：N47C

**[仓库预览版：recall-preview-1311bdd5](https://github.com/youq616/qbrain/releases/tag/recall-preview-1311bdd5)**，
选择 `qbrain-windows-x64-recall.zip` 并完整解压。ZIP SHA256：
`bc707db523de36b026ed302f4824afdbfd614bf8efbcc9a93a885f74d68fd3bc`。
原CI测试字节，未重打包、未签名；不是全项目完成的最终发行。
实际产品源码`1311bdd51b779e8da6b6420b62ea3f653edfa27f`，
[PR #18](https://github.com/youq616/qbrain/pull/18)已合并。
内部版本号不足以区分修复范围，以MANIFEST、完整源码SHA和外部摘要为准。
旧dist和固定旧哈希的N46E工具不是这个新包的安装路径。

[当前状态](CURRENT-STATUS.md) · [阶段复核](docs/nodes/N47C-HARD-AUDIT.md) ·
[测试证据](docs/nodes/n47c-evidence/SUMMARY.json) · [发布记录](docs/nodes/n47c-evidence/RELEASE.json)

## N47C：召回匹配事实，不隐藏直接冲突证据

`fact recall --query ...`与既有MCP `memory_read(view=recall,query=...)`按完整查询
子串匹配有效active用户原话。每个命中连同所有有效直接显式矛盾对方一起返回，
即使对方不含查询词，也不能略去。保留完整原话、revision、item/event/session来源
及confidence=null。不会把否定原话改为肯定，不推断真假或选择赢家。

```powershell
.\qbrain.exe fact recall --brain my-brain --source my-project --query "命令行" --limit 5 --max-bytes 8192
```

匹配先于候选上限，因此不会被100条无关新事实挤掉。关联只展开一层；若对方也匹配，
它仍保留自己的独立命中组与其他反证边。一个SQLite快照贯穿整组读取，调用内工作
预算和输出预算保持；放不下整组就标truncated，不截原话或返回半组。
空+truncated不是没有匹配；顺序是created_at/id，不是置信度或语义相关性排序。
[完整语义与免编译测试](docs/integration/FACT-RECALL.zh-CN.md)。

**本阶段未自动开启Hook事实注入。** Agent可主动使用这个读取接口；自动客户端
接入需要后续显式开关和总上下文预算，不因这个接口存在就声称已完成。

## 已有基础

N47B提供`fact conflicts`/`memory_read(view=conflicts)`成对查看显式冲突。
N47A提供完整原话与证据绑定的事实创建、同原话附加证据、撤回、替代和显式矛盾；
首次明确事实写入先备份，再初始化独立可选表，不覆盖旧facts。N47B/C无新迁移。
[事实生命周期](docs/integration/EVIDENCE-FACTS.zh-CN.md) ·
[成对冲突语义](docs/integration/CONFLICT-INSPECTION.zh-CN.md)。

会话归档、原文记忆、采集开关、来源隔离、重试去重、遗忘联动；Claude/Codex项目级
Hooks与可撤销安装；L0/L1摘录、单独许可的可选摘要、L2原文分页和缓存失效；六工具
MCP、精确有界向量候选、Embedding模型标签隔离、可靠批量队列与过期结果拒绝保持。
N46F中文/假名/韩文连续子串补充和共享不可变WinHTTP会话也保留；系统代理设置改变
后需重启进程。普通memory_read仍为原文子串，不因N47C改变既有视图的含义。

## 验证与边界

原生运行34854466927、34854466971必需任务通过：完整Windows51注册组，召回15场景/
330断言在Server2025/Server2022/portable通过，Windows/portable各44项CLI/MCP检查与
71次预期退出。旧事实、冲突、HTTP、队列、CJK、记忆、Hook、上下文及双PowerShell
门槛保留；两套Windows HTTP各81项，真实PG DSN仍明确SKIP，不计作PG集成验收。

阶段工程自审另有162项原始源码/日志/包回读、Clang ASan/UBSan实际单元和进程检查、
独立关系图与预算oracle180检查/294命令，以及两个准确失败的故障注入副本。
这些不是第三方审核、Windows sanitizer或实际已登录宿主验收。没有未解决的本阶段
P0/P1，不代表绝无任何潜在缺陷。哈希用于本地篡改检测，不是签名认证。

自动语义提取/冲突判断、衰减/画像、自动Hook事实召回、PG对等、完整ACL/DLP、真实
模型质量/费用、Codex宿主闭环与正式签名发行仍属于后续工作。项目尚未全部完成。

## 使用与数据

升级前备份脑库，完整解压同包并使用其中脚本。安装默认只召回；`-EnableCapture`
单独开启该项目本地采集，不自动开启Qbrain外部模型或MCP写授权。客户端信任和
工具权限仍正常确认，不绕过安全提示。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Install-QbrainMemory.ps1 -HostName Claude -ProjectPath "D:\Projects\MyProject" -Binary ".\qbrain.exe" -EnableCapture
```

Codex使用`-HostName Codex`；实际版本、认证与事件能力另行验证。默认数据位于
`%LOCALAPPDATA%\Qbrain\`，卸载保留记忆和备份。不要上传真实会话、数据库或密钥。
[安装/卸载](docs/integration/QUICKSTART.zh-CN.md) · [完整接入说明](docs/integration/WINDOWS-MEMORY.md)。

## 从源码构建与本地交接

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-cl.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-tests-cl.ps1 -SkipProductionBuild
```

源码构建需要MSVC；只有同轮生产构建成功且源码未变时才能跳过重复构建。运行
预编译包不需要编译器。Python是CI/验收工具依赖，不是新增产品服务。
本地Agent任务遵循[单提示词交接规则](LOCAL-AGENT-HANDOFF.md)：文件先放仓库，
固定来源、哈希与使用方法；不让本机并行重写同一代码或反复导出已接收源码。

## 历史与许可

[N47B](docs/nodes/N47B-HARD-AUDIT.md) · [N47A](docs/nodes/N47A-HARD-AUDIT.md) ·
[N46F](docs/nodes/N46F-HARD-AUDIT.md) · [N46D队列](docs/nodes/N46D-QUEUE-HARD-AUDIT.md)。
历史失败记录保留；[Issue #2](https://github.com/youq616/qbrain/issues/2)跟踪总路线。
MIT；保留[LICENSE](LICENSE)与[第三方许可说明](THIRD-PARTY-NOTICES.md)。默认本地
运行不表示开启外部模型以后资料仍不外发。
