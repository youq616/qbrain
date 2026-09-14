# N47D 本机真实客户端验收任务（尚未执行）

这里只验证新增加的事实 Hook 是否真正进入已登录客户端，不能继承 CI 的模型消费结论。
产品源码：`5275045c4790b802b620ba0af52ec6248cd587d5`。原生事件、安装器、回归已由仓库验证，不要求本机编译或重跑整套测试。
固定 Release：`hook-fact-preview-5275045c`，文件 `qbrain-windows-x64-hook-facts.zip`。
ZIP SHA256：`89918f2ed6964b4051d4542b7cd2358406423b6f3111db202e92e89e043086e8`；EXE SHA256：`cc544211b06dd4439cb79c69bf5baab190b831c97c9b87d911c8373bac8d7489`。
下载：`https://github.com/youq616/qbrain/releases/download/hook-fact-preview-5275045c/qbrain-windows-x64-hook-facts.zip`。
这是未签名开发预览，保留系统防护和正常信任确认，不绕过拦截。

## 范围与隔离

不修改生产源码或原工作区，不提交/push，不安装编译器、包管理器或客户端，不改 Codex
网关认证。只使用当前可正常启动的已登录 Claude Code，最多三个必要测试会话；Codex
有既有认证阻塞就单独记录，不拿 Claude 的结果替代。正常客户端模型调用使用已有授权；
不要启用 Qbrain 外部提取、Embedding 或摘要许可。

新建唯一临时目录，A、B 两个测试项目、两个不同 BrainId、reports 及 data 目录。报告和
准备脚本放在 A/B 之外。下载后先核对外部 ZIP 摘要，再完整解压、核对 MANIFEST 中的
源码、EXE 摘要以及每个文件哈希。禁止 old dist、N46E旧固定包或散落 EXE 替代。
使用包内 `Invoke-QbrainJson.ps1` 的 UTF-8 stdin 传输，不用 PowerShell 默认编码管道。

仅给安装器和测试客户端子进程设置一致的测试 LOCALAPPDATA=data；清除继承的 QBRAIN
生产数据库/Brain选择变量。不要改系统/用户持久环境，不清空 HOME/USERPROFILE 或
客户端登录变量，不打印密钥。不复制真实认证文件到测试包；若无法同时保留客户端
登录与脑库隔离，明确 BLOCKED，不改用真实脑库。禁止读正式项目、个人历史聊天或全盘扫描。

## 生成独立事实与安装

在 A 的专用脑库、source=default 中，用程序当场生成两个不同随机标记，例如
`QBD47-A-<random>` 与 `QBD47-B-<random>`。以两个独立合成事件手动归档以下原话：
`I prefer the log prefix <A随机值>.` 和 `I prefer the log prefix <B随机值>.`。
使用 memory extract 的本地规则提取，随后 memory read 读取真实 item_id，再用 fact create
建立两个 `predicate=preference.log_prefix` 的完整原话事实，最后 fact contradict 写入显式关系。
不得直接写 SQL 制造事实，也不把手动种子步骤声称为自动采集/自动事实抽取。

安装 A、B 时使用同包 EXE 与脚本、各自 BrainId、-HostName Claude 和 -EnableFactRecall，
不传 -EnableCapture。验证 Status 的 installed、configuration_matches、fact_recall_enabled。
B 保持空脑库。随机答案只在本次合成脑库与项目外报告中，不写进 README、AGENTS.md、
CLAUDE.md、项目文件、客户端启动附加上下文或提问中。配置可以包含BrainId，但不含答案。

## 三次真实会话与证据区分

先查看本机实际版本和 --help，采用该版本正常方式启动真正独立的会话，不 resume 旧会话，
不绕过客户端嵌套运行限制、Hook信任或工具审批。不允许用父Agent已有上下文或普通子代理
替代能触发项目 SessionStart 的真实客户端会话。遇到必须手动确认的步骤只指出具体操作。

A1：在 A 启动新会话，询问：
“只根据本会话自动提供的 Qbrain 上下文，这个测试项目的 log prefix 有哪些已记录偏好？
如有冲突请完整并列，不自行选一个，并注明来源。不要调用工具或读取文件寻找答案。”
应同时呈现两条随机原话或两个标记，并承认存在已明确记录的冲突。问题中不得带入答案。
分别记录真实 Hook 事件、输出上下文、最后回答和是否调用工具；若只观察到正确回答而
未观察到 Hook 内部输出，标注证据边界，不将模型自述来源当作完整事件日志。

随后在客户端之外仅忘记 A随机值对应的种子事件，核对另一事实仍有证据。结束 A1，
在 A 启动独立新会话 A2，提问同样的问题。新的自动上下文不应再含已经遗忘的 A随机值，
B随机值应仍可见。不删除另一个事件、不复用原上下文。这里每个原话只有一个支持事件，
避免“独立未遗忘副本”使逐事件遗忘测试含糊。

B1：在 B 启动新会话，提出同样问题，应表示没有该项目的已记录偏好，不得获得 A 的任一
随机标记。不得读 A、reports、父Agent记录、其他脑库或全局历史。模型一旦调用 MCP/文件
读取得到答案，单列主动读取，不算本项的纯自动 Hook 消费。最多这三次会话，不重试到绿。

只收集本次会话的脱敏客户端日志/调用摘要。可用当前客户端支持的日志方式观察，不能
修改安装器拥有的Hook命令来偷加日志包装、绕过权限或影响正常撤销。trace的
host_consumption_confirmed=false只是“程序无客户端消费证明”，不要手动改为true。
recall_bytes是每次完整Hook JSON预算，不是所有会话、所有模型上下文或Token总预算。

## 关闭、撤销与报告

在 A 重新安装但不传 -EnableFactRecall，核对开关为false；旧普通记忆仍可能按原规则
召回，所以不能以“关闭事实开关后完全不知道任何原话”作为断言。然后卸载本次 A/B 接入，
核对各自 installed=false，正式项目与全局客户端配置未变，保留本次合成诊断证据。

输出 report.md、summary.json、issues.md，并合成一个 `qbrain-n47d-live-acceptance.zip`。
记录真实OS/客户端版本、源码/EXE哈希、逐项 PASS/FAIL/BLOCKED/NOT_RUN、未覆盖边界、
A1/A2/B1实际观察与工具调用情况；状态总数从逐项记录计算。只打包脱敏报告及必要的本次
合成会话摘要，不含数据库、EXE、认证、个人聊天或完整仓库，不上传公开仓库。
本地不修代码，源码缺陷给最小复现和证据交仓库端处理。最终提供一个ZIP的绝对路径、
大小和SHA256，说明是否确有最小人工信任确认事项，不要求重复已有CI或先安装开发环境。
