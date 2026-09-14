# Qbrain

Windows 原生 C++20 / PowerShell Agent 记忆与知识库，默认 SQLite + FTS5。
不要求 Docker、WSL 或 Python 服务。由 `Lordakee/qbrain` 的 MIT 代码继续开发；
gbrain / OpenViking 是设计参考，不是完整功能等价声明。

## 当前已发布开发版：N47B

**[仓库预览版：conflict-preview-7999d39b](https://github.com/youq616/qbrain/releases/tag/conflict-preview-7999d39b)**，
选择 `qbrain-windows-x64-conflicts.zip` 并完整解压，SHA256：
`ceb1ad45109a1cdf7a5f72a4982465613ac4119c479025f6e45b139f01014e0c`。
包为原 CI 测试字节，未重打包、未签名；不是整个项目完成的最终发行版。
实际测试源码 `7999d39b9e6a253d62557a6ccc8341598ccdebb6`，
[PR #17](https://github.com/youq616/qbrain/pull/17) 已合并。
内部版本号不足以识别改动范围，以包内 MANIFEST、完整源码 SHA 和外部摘要为准。
旧 `dist/` 和固定旧哈希的 N46E 验收入口不是本次新包的安装路径。

[当前状态](CURRENT-STATUS.md) · [N47B阶段复核](docs/nodes/N47B-HARD-AUDIT.md) ·
[测试证据](docs/nodes/n47b-evidence/SUMMARY.json) · [发布记录](docs/nodes/n47b-evidence/RELEASE.json)

## 本轮新增：成对查看显式冲突

`fact conflicts` 与现有 `memory_read(view=conflicts)` 返回明确记录的矛盾双方，
包括完整用户原话、当前 revision 和 event/item/session 证据来源。只返回两个
active且均有有效证据的事实；不截断成半对，不自动判断真假或选胜者。
来源权限、单快照一致性、按字节/数量/证据工作的限制保持。

若读取中另一连接提交遗忘，当前读取仍可能看到原快照完整对，下次调用观察删除。
空结果带 `truncated=true` 不表示没有冲突；可缩小predicate/ID范围或增大预算。
读取不建表、不备份、不写入，不增加模型外发、Hook注入或MCP工具名称。
[完整调用与语义](docs/integration/CONFLICT-INSPECTION.zh-CN.md)。

N47A 已有事实创建、同原话附加证据、撤回、替代与显式矛盾关系。事实不是模型判断：
只保存证据支持的完整用户原话，confidence=null。首次明确写入事实时先备份脑库，
再初始化独立可选表，不覆盖历史facts表；N47B没有新迁移。
[N47A事实说明](docs/integration/EVIDENCE-FACTS.zh-CN.md)。

## 现有基础能力

会话归档与原文记忆；采集开关、来源隔离、重试去重、遗忘联动；Claude/Codex项目级
Hooks与可撤销安装；L0/L1摘录、单独许可的可选摘要、L2原文分页和缓存失效；六工具
MCP；精确有界向量候选、Embedding模型标签隔离、可靠批量队列及过期结果拒绝。

N46F中文/假名/韩文连续字串搜索补充保持，普通memory_read仍是连续原文匹配。
WinHTTP共享不可变会话，连接、认证头、正文、回调与时限逐请求隔离；系统代理设置
改变后需重启进程。不是全局凭据缓存或关闭TLS检查。

## 验证与边界

产品运行34798495285及34798495355通过：完整Windows50个注册组，冲突13场景/346
断言在Server2025/Server2022/portable通过，Windows/portable的38项CLI/MCP检查与
75次命令均符合预期退出。原N47A、队列、CJK、Embedding、记忆、Hook、上下文和
双PowerShell门槛保持；两套Windows HTTP各81项，真实PostgreSQL DSN用例明确SKIP。

阶段复核另有134项源码/日志/包回读，Linux Clang ASan/UBSan实际冲突单元与进程检查。
这是所有者授权的单独工程自审，不冒充外部子代理审核；N47A原始独立报告仍保留。
有限合成测试不是全场景质量、成本或零泄漏保证，未重做用户已登录客户端验收。

自动语义提取/冲突判断、衰减/画像、自动事实召回、PG对等、完整ACL/DLP、真实模型
质量/费用、Codex登录宿主闭环和正式签名发行仍需后续开发或验收。

## 使用与数据

升级前备份已有脑库；完整解压同一开发包，使用其中脚本。安装默认只召回，
`-EnableCapture` 单独开启该项目本地采集，不自动开启Qbrain外部模型或MCP写授权。
客户端项目/Hook信任须正常确认，不绕过安全提示。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Install-QbrainMemory.ps1 -HostName Claude -ProjectPath "D:\Projects\MyProject" -Binary ".\qbrain.exe" -EnableCapture
```

Codex使用`-HostName Codex`，版本、认证和事件能力另行验证。默认数据位于
`%LOCALAPPDATA%\Qbrain\`，卸载保留记忆与备份，不上传真实会话、数据库或密钥。
[中文安装卸载](docs/integration/QUICKSTART.zh-CN.md) · [完整接入说明](docs/integration/WINDOWS-MEMORY.md)。

## 从源码构建与交接

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-cl.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-tests-cl.ps1 -SkipProductionBuild
```

源码构建需要MSVC。只在同轮生产构建成功且源码未变时跳过重复构建。运行预编译包
不要求安装编译器；Python是CI/验收工具依赖，不是产品必需服务。
本地Agent任务按[单提示词交接规则](LOCAL-AGENT-HANDOFF.md)，文件先放仓库并固定
来源、哈希和用法，不让本机并行改同一代码或反复导出已接收的源码。

## 历史与许可

[N47A](docs/nodes/N47A-HARD-AUDIT.md) · [N46F](docs/nodes/N46F-HARD-AUDIT.md) ·
[N46D队列](docs/nodes/N46D-QUEUE-HARD-AUDIT.md) · [N46C](docs/nodes/N46C-HARD-AUDIT.md)。
历史失败和范围限制保留；[Issue #2](https://github.com/youq616/qbrain/issues/2)继续跟踪总路线。
MIT；保留[LICENSE](LICENSE)与[第三方许可说明](THIRD-PARTY-NOTICES.md)。
默认本地运行不表示开启外部模型后资料仍不外发。
