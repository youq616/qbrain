# N47E 本机任务 v2：真实输入自动整理为事实并在新会话召回

这是唯一新本机任务，不重复已通过的 N47D 手工种子验收。N47D 报告已收到；其
5275045c / Claude 2.1.270 / Server 2022 结果不认证新的 N47E 自动采集整理路径。
本任务是原 e1857c49 任务的精确证据补充，不改变 c6c76a2f 产品或安装器字节。

## 固定产品与隔离

从仓库下载 https://github.com/youq616/qbrain/releases/download/promotion-preview-c6c76a2f/qbrain-windows-x64-promotion.zip 。
ZIP 必须为 1986872 字节，SHA256：
50395502dbcf65d142fd36a0f511dc8b764971bcfd5854d466e8d2e38e04ae73。
产品源码 c6c76a2f3fd2dd0b07326ef6e19c1a59283402e8，源树
07f00ef07fc1cb79642472b63052221c84bb2db1；EXE 3965952 字节，SHA256：
f9ed4d157f46e5ee25fc1f92449a805b1c9a51bdf65faf9a42b443c9266e2c29。

仅在新建唯一目录校验后完整解压，核对 MANIFEST 的全部文件和源码，阅读同包
LOCAL-FACT-PROMOTION.zh-CN.md。不能改用旧包/dist/latest或绕过哈希、防护和信任。
不用编译器、Docker、winget/choco、GitHub 写凭据或源码修改。已有完全相同版本、
相同完整自动链路的合格验收时直接交付现有报告，不再制造重复会话。

用现有正常登录的 Claude Code，先确认实际客户端版本/命令能力。不改 Codex 认证，
其原401阻塞单独记录，不读写key、不切provider。不得绕过项目、工具或嵌套限制。

在仓库外新建项目A/B、不同且唯一的BrainId和专用数据根，报告在项目之外。
同包安装器与随后客户端/Hook/MCP子进程必须使用同一测试LOCALAPPDATA，清除继承的
Qbrain生产脑库/数据库选择变量，不改持久环境变量。保留客户端正常登录所需
HOME/USERPROFILE/认证环境，不扫描凭据或真实聊天。无法同时保证隔离与登录则
BLOCKED，不能用真实脑库。Qbrain测试可设QBRAIN_EMBED_MOCK=1；不启用Qbrain外部
提取/摘要/Embedding。已登录客户端的正常模型请求仍会外发，不称整体无模型调用。

## 安装及恰好至多三段真实会话

A用同包scripts/Install-QbrainMemory.ps1，显式-EnableCapture -EnableFactPromotion
-EnableFactRecall。B用另一空脑库，只-EnableFactRecall，不采集、不整理。记录Status
的有效状态；普通安装/初始化空库不是人工造事实，不得预填A的偏好。

A1：当场生成QBN47E-<随机串>。输入“我偏好本测试项目的日志前缀为<随机标记>。
不要写入README、AGENTS.md、CLAUDE.md或其他项目文件，不要调用记忆写入工具，
仅确认收到。”必须用真正客户端UserPromptSubmit自动完成采集、local提取和promotion。
禁止父代理或模型执行memory capture/extract、fact create/promote、写SQL或合成Hook
事件来替代这段路径。模型只确认，不调用工具。结束后父代理只读核对事件、提取方法
explicit-markers-v1、memory.preference事实和完整A1原话的item/event绑定。记录实际
Hook/客户端转录。Stop可能覆盖last-trace，不把末尾not_run当成此前未执行；也不能
手改trace中的host_consumption_confirmed。

A2：关闭A1，启动另一真正独立新会话，不resume/continue或继承父代理上下文。只问
“本测试项目中，我偏好的日志前缀是什么？请根据自动提供的Qbrain上下文回答并说明
来源，没有就说不知道。”不得在启动参数、提问、项目文件、额外上下文提供答案。
模型不得主动调用MCP、读文件、旧转录或报告找答案。优先检查SessionStart事实上下文，
对照准确答案与来源；若实际有主动工具读取，单独标注，不能判为纯自动Hook消费。

B1：在项目B启动全新会话，提同样问题，不给标记、不读取A/报告。它应不知道；只读
核对B的空库及自己Hook内容。模型猜中本身不证明串库，必须定位数据来源。

每个会话只执行一次，最多三次，不重试到碰巧成功。不更改全局Agent设置或包装/
修改安装器拥有的Hook命令。客户端限制/信任确认需人工时只指出最少操作，其余可
执行检查继续。不要把Server2022称Win11，也不要拿Claude结果代替Codex。

## 结构化证据，避免子串误判

N47D附件的contains_recorded_conflict在A2为true，因为no_live_recorded_conflict也
包含该子串。不得用这样的文本包含检查判定冲突状态。优先读取
fact_groups[i].conflict_state的完整值，检查contradictions数组，而不是搜索模型
回答、用户原话或任意文本中的recorded_conflict。无法取得字段时记录NOT_OBSERVED
或text_presence_only，不捏造为结构化证据。保留原始可得证据与其来源，不改历史报告。

仓库提供只读助手tools/acceptance/inspect_hook_context.py，Python 3.10+标准库即可。
助手SHA256：46817e5e2eac23de06d5b8b1d433ef57499d5d5367293d93bed80f7e3ebde355。
只使用交接提示词指定的同一固定提交下载它，哈希一致后才运行。它只解释已取得的
原始Hook JSON或已经解码的additionalContext，不读取客户端历史、不启动程序、不回显
原话，不认证客户端/模型消费或事实真实性。不要为调用它而补造JSON、改Hook命令或
额外启动模型会话。仅有脱敏字段摘要时保留摘要及证据限制，助手可NOT_RUN。

原始Hook输出已合法可得时：
`python -B inspect_hook_context.py --input <本轮合成Hook输出.json> --report <全新输出.json>`
只有已解码additionalContext原始文本时，加`--format additional-context`。输出INSPECTED
只表示字段读取成功，不是验收PASS；REJECTED不是直接判定产品缺陷，应核查输入形式。
拒绝旧普通记忆格式是助手的声明范围，不把它当作Qbrain旧接口错误。
空{}或空且truncated不会认证不存在记忆/冲突。

## 关闭、卸载和单一报告

A重装不带三个启用开关，核对有效关闭；再卸载本次A/B接入，只清自有条目，保留合成
诊断脑库、原工作区、其他插件和全局设置。关闭开关不会删除既有事实，不要求额外
模型会话来证明“完全失忆”。不反复执行已通过的N47D全部流程。

逐项分开记录采集、local提取、自动promotion、事实原文/来源、独立上下文、模型消费、
B隔离、关闭与撤销。summary.json数量从唯一ID检查列表计算，包含PASS/FAIL/BLOCKED/
NOT_RUN/SKIP，正文与机器计数一致；注明原始完整Hook JSON、结构化字段摘要、精确
标记检查和模型自述分别取得了什么，不能互相替代。无原始转录就不得声称逐字节比对。

输出report.md、summary.json、issues.md、handoff.json与必要脱敏日志，只打包一个
qbrain-n47e-local-acceptance.zip。仅包含本次合成资料，不含数据库、EXE、完整仓库、
密钥、认证、个人聊天或非必要费用/用量元数据；不自动公开上传。源缺陷给最小复现
交仓库端，不本地并行修。最终给实际结果、边界和ZIP绝对路径/大小/SHA256。
