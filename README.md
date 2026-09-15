# Qbrain

Windows 原生 C++20 / PowerShell Agent 记忆与知识库，默认SQLite + FTS5。
不要求Docker、WSL或Python服务。由Lordakee/qbrain的MIT代码继续开发；
gbrain / OpenViking是设计参考，不代表完整功能等价。

## 当前开发预览：N47E

[仓库 Release：promotion-preview-c6c76a2f](https://github.com/youq616/qbrain/releases/tag/promotion-preview-c6c76a2f)
选择 `qbrain-windows-x64-promotion.zip`，完整解压。SHA256：
`50395502dbcf65d142fd36a0f511dc8b764971bcfd5854d466e8d2e38e04ae73`。
原CI测试字节，未重新打包、未签名；不是全项目完成的正式发行。
实际源码`c6c76a2f3fd2dd0b07326ef6e19c1a59283402e8`；
[PR #20](https://github.com/youq616/qbrain/pull/20)已合并。
以MANIFEST、完整源码SHA和外部摘要识别版本，不用历史dist或旧固定哈希工具替代。

[当前状态](CURRENT-STATUS.md) · [阶段复核](docs/nodes/N47E-HARD-AUDIT.md) ·
[测试摘要](docs/nodes/n47e-evidence/SUMMARY.json) · [发布记录](docs/nodes/n47e-evidence/RELEASE.json)

## 新增：本地提取事件自动整理为证据事实

`-EnableFactPromotion`独立默认关闭，要求`-EnableCapture`。开启后，当前用户事件
成功local提取的完整原话自动成为证据绑定事实，不需要再逐条手工fact create。
整理使用固定memory.<category>标签、confidence=null，保留原话中的否定和上下文，
不推断真假、不生成新的语义矛盾、不调用额外模型。事实召回仍需独立开关。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Install-QbrainMemory.ps1 -HostName Claude -ProjectPath "D:\Projects\MyProject" -Binary ".\qbrain.exe" -EnableCapture -EnableFactPromotion -EnableFactRecall
```

仅需原记忆采集，不传promotion/recall开关。仅需事实召回，可以单独启用
`-EnableFactRecall`而不采集；promotion不能在未授权采集时自动开启。Status报告
有效值，重装不传开关即关闭。卸载保留脑库/备份，不因关闭就撤销已存在的事实。
[本地整理语义](docs/integration/LOCAL-FACT-PROMOTION.zh-CN.md) ·
[Hook事实与统一预算](docs/integration/HOOK-FACT-RECALL.zh-CN.md)。

也可主动调用`fact promote --event ID`或既有MCP memory_write的fact_promote动作，
来源和写授权照旧。每批最多32条原始证据；相同独立原话追加支持，重放不增版本。
退休同句事实阻止自动复活，16条物理支持上限不会产生新的溢出事实。

所有旧支持过期后，新的有效独立原话只能在旧支持全部完整且已过期时续接仍active
事实。旧过期时间不重置，旧支持不重新出现在live结果中；退休或部分损坏的历史仍
拒绝。事实/证据批次原子；既有备份及可选schema准备是单独步骤，失败后可能保留。

## 证据、预算与隐私边界

N47D的事实与普通记忆共用SQLite快照及完整Hook JSON响应预算；事实和直接显式
反证不能拆半组。recall_bytes不是会话Token总预算，候选上限不是SQL耗时保证。
事实每次重验，过期/删除/篡改/来源校验持续有效，不把原话写入trace或去重状态。

**Hook上下文交给已授权客户端，客户端可能发送至其模型。** 没有额外Qbrain模型调用
不等于没有客户端外发。不改认证/全局Agent配置，不绕过信任或安全软件。
逐事件forget不安全擦除备份、WAL、客户端旧上下文或其他独立未遗忘的同句事件。
原文哈希是本地一致性检查，不是数字签名或完整多用户权限体系。

## 已有能力

N47A事实创建/附加支持/撤回/替代/显式矛盾，首次明确事实写入先备份并初始化独立
可选表，不替换历史facts。N47B成对冲突查看；N47C查询召回保留直接反证；N47D显式
Hook接入与统一输出预算保持。N47E无新迁移、MCP名称或模型许可。
[事实](docs/integration/EVIDENCE-FACTS.zh-CN.md) · [冲突](docs/integration/CONFLICT-INSPECTION.zh-CN.md) ·
[主动召回](docs/integration/FACT-RECALL.zh-CN.md)。

会话归档/记忆、来源隔离、采集开关、重试去重、遗忘联动、项目Hook与可撤销安装，
L0/L1摘录、单独许可的可选摘要、L2分页、缓存失效、六工具MCP，CJK连续子串搜索、
精确有界向量候选、Embedding模型标签隔离、批量队列和过期结果拒绝全部保持。
HTTP共享不可变会话与逐请求状态保持，系统代理设置改变后需重启进程。

## 验证与尚未验收部分

原生34906704753/34906704707必需任务通过：Windows53组，新整理单元两Windows版本
及portable各18场景237断言，实际EXE CLI/MCP/Hook夹具68项77命令，PS5.1/7安装各33项。
旧事实/冲突/召回/Hook/HTTP/队列/CJK/记忆和双PowerShell门槛保持；真实PG DSN明确SKIP。

单独工程复核包括Clang17 ASan/UBSan实际单元与进程、47事件/218命令独立状态oracle、
两个准确失败的故障副本、96项报告门槛、216项原始源码/日志/包回读。未发现本阶段
未解决P0/P1，不是绝对无缺陷保证、第三方/子代理审核或Windows sanitizer认证。

**合成事件夹具不等于真实已登录客户端。** 按[唯一新本机任务](docs/integration/N47E-LOCAL-ACCEPTANCE.zh-CN.md)
用至多三次隔离Claude新会话验证真实自动采集→提取→整理→新会话召回及项目隔离。
不需编译器、GitHub写凭据或重复源码审核；Codex既有401仍单独阻塞，不改其认证。

通用语义提取/冲突判断、衰减画像、PG对等、完整ACL/DLP、真实模型质量费用、正式
签名与整个融合项目完成仍未声明。默认本地运行不表示启用外部模型后资料仍不外发。

## 从源码构建、数据与交接

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-cl.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-tests-cl.ps1 -SkipProductionBuild
```

源码构建需要MSVC；仅同轮生产构建成功且源码未变时跳过重复构建。运行预编译包
不要求编译器，Python是CI/验收依赖而非产品服务。升级前备份脑库，完整解压同包，
默认数据为`%LOCALAPPDATA%\Qbrain\`；不上传真实聊天、数据库或密钥。
[完整安装](docs/integration/QUICKSTART.zh-CN.md) · [接入细则](docs/integration/WINDOWS-MEMORY.md)。
本机任务只给一个完整提示词，文件先放仓库并提供固定地址/摘要/用法，遵循
[交接规则](LOCAL-AGENT-HANDOFF.md)，不让本机并行重写相同代码。

## 历史与许可

[N47D](docs/nodes/N47D-HARD-AUDIT.md) · [N47C](docs/nodes/N47C-HARD-AUDIT.md) ·
[N47B](docs/nodes/N47B-HARD-AUDIT.md) · [N47A](docs/nodes/N47A-HARD-AUDIT.md) ·
[N46F](docs/nodes/N46F-HARD-AUDIT.md)。
[Issue #2](https://github.com/youq616/qbrain/issues/2)继续跟踪总路线，历史失败保留。
MIT；保留[LICENSE](LICENSE)及[第三方许可](THIRD-PARTY-NOTICES.md)。
