# Qbrain 当前交付状态

## N47D：仓库开发、阶段审核、合并与预览发布已完成

[PR #19](https://github.com/youq616/qbrain/pull/19) 已合并，产品合并提交：
`d7e29df4acfbf7d47e09efe02fed7297578e4362`。
实际产品、原生测试和单独工程审核源码：`5275045c4790b802b620ba0af52ec6248cd587d5`，
树 `7cd4ab256aa8dd885a95c00f8de712512933421a`。
审核头649b7b4只增加/更新5个文档，合并与审核头零文件差异。后续交付说明不改变EXE。

[仓库预览 Release：hook-fact-preview-5275045c](https://github.com/youq616/qbrain/releases/tag/hook-fact-preview-5275045c)
已公开。选择 `qbrain-windows-x64-hook-facts.zip`，1960966字节，SHA256：
`89918f2ed6964b4051d4542b7cd2358406423b6f3111db202e92e89e043086e8`。
EXE SHA256：`cc544211b06dd4439cb79c69bf5baab190b831c97c9b87d911c8373bac8d7489`。
完整解压阅读 `HOOK-FACT-RECALL.zh-CN.md`。未签名开发预览，不需本机编译器。
旧N46E固定哈希工具不接受新包，不能绕过校验或用历史dist代替。

## 实际新增能力与默认值

安装器新增 `-EnableFactRecall`，默认关闭、独立于 `-EnableCapture`。Status显示
fact_recall_enabled，重装不传开关即关闭。旧项目配置没有fact_recall字段时保留原Hook。
明确开启后，SessionStart提供近期有效事实，UserPromptSubmit按现有字面词提取召回。
已有完整直接冲突组优先，普通记忆使用剩余同一个序列化Hook JSON预算与条数限制。

整组放不下不截原话、不只返回一侧。普通记忆排除同源现有事实的绑定项及完全相同
原话，含退休事实，防止从另一条路径绕过反证/撤回。事实每次重新核验，不因会话
去重隐藏revision/支持证据变化。一个SQLite读快照贯穿两条路径，读取结束后才采集。

没有新数据库迁移、自动事实创建、语义判断、真假赢家、新MCP名称或写权限。
recall_bytes是每次完整Hook响应，不是会话Token总量。事实证据工作有共享限制，
但没有SQL总扫描成本或硬实时承诺。空结果带truncated表示不完整。
逐事件遗忘不删除其他独立未遗忘的同句记录；历史客户端上下文和备份也不被抹除。

**开启会将数据提供给用户已授权客户端，客户端可能发送至其模型。** 没有额外Qbrain
模型调用不表示客户端无外发。未改变外部提取/摘要许可、认证或全局客户端设置。

## 已核实的原生与单独工程审核

开发34862423429与N42的34862423691必需任务通过：52个准确Windows注册组，新组合
单元在Server2025/Server2022/portable各13场景229断言，Windows/portable新Hook事件
夹具52项72命令；PowerShell5.1/7新开关安装各33项。全部旧事实/冲突/召回/HTTP/队列/
CJK/记忆/Hook/上下文/双PowerShell门槛保持，真实PG DSN明确SKIP。

单独自审还有Clang17 ASan/UBSan对SQLite C和C++实际单元/进程执行，组合对照126种
配置、1178断言、176次命令在GCC和sanitizer均通过，两个故意破坏临时副本准确失败。
82项报告门槛和187项原始源码/日志/包回读通过，745文件源树重建一致。没有发现本阶段
P0/P1阻塞，不是绝对无缺陷保证、第三方审核或真正独立子代理审核。

发布34866105622成功：核对合并/审核头、固定源码/原始CI/完整单元与安装报告，上传
新草稿后下载逐字节核对三项资产再公开。未重编译、未重新打包或覆盖旧Release。
通用未审核自动发布仍未开启。

[阶段复核](docs/nodes/N47D-HARD-AUDIT.md) · [测试摘要](docs/nodes/n47d-evidence/SUMMARY.json) ·
[发布记录](docs/nodes/n47d-evidence/RELEASE.json)

## 本机还需完成的唯一新边界

**真实已登录客户端消费尚未验收。** 原生事件夹具和安装检查不等于客户端实际加载、
模型确实使用了上下文；trace的host_consumption_confirmed仍保留false。
只需按[固定本机任务](docs/integration/N47D-LOCAL-ACCEPTANCE.zh-CN.md)用现有Claude登录，
三个隔离新会话验证两条冲突并列、遗忘后更新和另项目不串记忆，然后关闭/卸载。
不安装编译器、不修改源码、不配GitHub写凭据、不重审或重做整套CI。Codex既有认证
阻塞单独记录，不改认证、不用Claude结果冒充Codex通过。报告只交一个脱敏ZIP。

## 后续范围

N46F检索/HTTP、N47A证据事实生命周期、N47B冲突查询、N47C主动召回能力均保留。
自动语义提取/冲突判断、衰减画像、PG对等、真实模型质量费用、完整ACL/DLP、实际
Codex闭环与正式签名仍需后续开发/验收。仓库N47D完成不等于整个项目已完成。
