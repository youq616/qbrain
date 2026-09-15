# N47E 唯一本机任务：真实客户端自动采集→事实整理→新会话召回

只使用 Windows 原生 youq616/qbrain。本文件是验收任务，不是已通过的报告。
仓库原生测试和代码审核已覆盖构建、事务、证据过期续接、安装和合成Hook；本机仅补
真实已登录客户端实际触发和消费，不重新审核代码或重跑整个CI，不并行改生产源码。
最多三次必要的全新Claude会话；Codex既有401单独记录，不读写其密钥或切换provider。

## 固定文件与校验

发布标签：promotion-preview-c6c76a2f（须已公开，否则停止下载并记录阻塞）。
产品源码：c6c76a2f3fd2dd0b07326ef6e19c1a59283402e8。
产品源树：07f00ef07fc1cb79642472b63052221c84bb2db1。
下载地址：
https://github.com/youq616/qbrain/releases/download/promotion-preview-c6c76a2f/qbrain-windows-x64-promotion.zip
ZIP：1986872字节，SHA256
50395502dbcf65d142fd36a0f511dc8b764971bcfd5854d466e8d2e38e04ae73。
EXE：3965952字节，SHA256
f9ed4d157f46e5ee25fc1f92449a805b1c9a51bdf65faf9a42b443c9266e2c29。

在仓库之外创建唯一临时目录，由本地Agent自己下载。只接受上述固定ZIP原字节；
哈希不符或下载失败立即停止，不用latest、旧dist或旧N46E包替代。完整解压到新目录，
复核MANIFEST、EXE和安装器文件摘要，阅读LOCAL-FACT-PROMOTION.zh-CN.md和
HOOK-FACT-RECALL.zh-CN.md。未签名不等于不安全，也不允许关闭系统防护或绕过信任。
本模式不需要MSVC、Windows SDK、CMake、Docker、winget或GitHub写凭据。

## 隔离与安装

确认当前真实系统及Claude版本/帮助/正常登录，仅调用客户端验证状态，不打印认证
文件、key、网关私密地址或个人历史。保留真实客户端所需HOME/USERPROFILE和认证环境；
仅为安装器及客户端/Qbrain子进程使用同一个专用LOCALAPPDATA，清除继承的Qbrain
生产数据库选择变量。不能保证数据隔离与登录并存时记录BLOCKED，不用真实脑库替代。
不得更改持久用户/系统环境变量或全局客户端设置。

新建项目A/B和不同BrainId，全部位于此次新目录；报告目录在A/B之外。使用同包
scripts/Install-QbrainMemory.ps1。A显式启用-EnableCapture -EnableFactPromotion
-EnableFactRecall；B使用另一空脑库，只开启-EnableFactRecall。先运行Status记录有效
状态。安装器和随后客户端派生的Hook/MCP必须看到同一测试数据根。正常确认项目和
Hook信任，不添加跳过审批或沙箱的参数。

## 三段真实新会话

1. A1：当场生成随机前缀QBN47E-<随机串>。输入“我偏好本测试项目的日志前缀为
<随机串>。不要写入README、AGENTS.md、CLAUDE.md或其他项目文件，不要调用记忆写入
工具，仅确认收到。”不要预先调用memory capture、extract、fact create/promote或
合成Hook来代替这段自动路径。会话结束后只读核对实际事件、提取方法、memory.preference
事实和证据对应A1原话；确认新事实由真实UserPromptSubmit完成，而非模型工具写入。
保留实际调用和测试目录下的trace；后续Stop可能覆盖last-trace，不能只凭最后一次
not_run否定此前事件。不得改trace中的host_consumption_confirmed字段伪造通过。

2. A2：结束A1后启动真正独立的新会话，不resume、不continue。仅问“本测试项目中，
我偏好的日志前缀是什么？请根据自动提供的Qbrain上下文回答并说明来源，没有就说
不知道。”启动参数、问题、项目文件及附加说明不得包含答案，不允许读取报告、旧
客户端转录或其他脑库找答案。优先只检验SessionStart自动提供的事实，不用主动MCP
读取替代自动路径。记录准确答案及来源、实际Hook输出/事件与事实证据。

3. B1：项目B全新会话提出同样问题，不提供随机答案、不读取A或报告目录，验证其
无法从B的Qbrain连接取得A的专用偏好。B的空脑库和源数据也作只读核对。找不到应
明确不知道；模型猜对不自动判串库，须有数据来源证据。

每段仅执行一次正常会话，不循环重试到碰巧回答正确。认证、信任或客户端能力阻塞
分别标记，继续完成不受影响的非模型检查；真正需要人工确认时只指出最小操作。
不要把Claude结果算成Codex通过，也不要将Server2022称为Win11用户桌面验收。

## 关闭、卸载和报告

完成后将A重装为不传三个启用开关，确认有效状态关闭，再卸载本次A/B接入；仅撤销
本次拥有的条目，保留其他插件、全局配置和真实脑库。关闭不删除既有合成事实；这与
retract/forget是不同动作。不要求额外模型会话来重测CI已覆盖的安装开关。

分别记录：真实Hook触发、采集、local提取、自动promotion、独立新会话上下文、模型
消费、项目B隔离、关闭/卸载。区分PASS/FAIL/BLOCKED/NOT_RUN；总数由检查列表计算。
无真实消费证据时不认证消费，保留失败复现交仓库端，不在本机修代码或改断言。

在源码和项目外生成report.md、summary.json、issues.md、handoff.json及必要脱敏日志，
只打包一个qbrain-n47e-local-acceptance.zip。包含版本/包/EXE摘要、真实命令退出状态、
三个会话标识与结果、最小问题证据；只含合成测试资料，不含数据库、EXE、完整仓库、
密钥、认证文件或个人聊天，不自动上传公开GitHub。最后给出ZIP绝对路径、SHA256、
实际通过/阻塞项和最小人工操作，供用户上传到当前会话即可。
