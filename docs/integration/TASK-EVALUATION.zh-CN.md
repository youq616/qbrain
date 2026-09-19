# N47Q 跨会话任务评测

这是一套开发/验收工具，不是新记忆算法，也不是已经获得真实模型分数的报告。
它执行 Qbrain 真实 CLI/Hook 进程，建立合成对话、结束旧会话、读取新会话的上下文，
并导出后续模型评估所需的任务包和独立答案文件。不会登录客户端或调用付费模型。

## 能测什么，不能证明什么

50 项固定任务由 10 类场景 × 5 个中文主题组成：偏好召回、重复事件、遗忘、显式
替代、显式冲突、归档/恢复、两个项目与脑库隔离、助手角色排除、关闭采集、预算不足。
每项任务使用新随机标记；问题本身没有答案标记。初始化记忆走 UserPromptSubmit
自动采集/本地提取/整理，不写数据库测试夹具；替代、冲突与归档仍是显式操作。

这验证的是小规模、规则标记型数据的证据和生命周期，不是 50 种独立能力、通用中文
理解、多跳推理或百万条记忆性能。--host 只选择事件格式，不运行该真实宿主。
上下文包里的 delivery_truncated 来自已核对的诊断元数据；这是评估器补充信息，
不能声称真实宿主或模型已自动读取该字段。暂不覆盖对抗性提示注入评测。

## 运行引擎评测

需要 Python 3.10 或更高版本作为测试工具、完整仓库源码和一个已校验的 Qbrain
可执行文件。不要求将 Python 装成 Qbrain 运行服务，也不修改真实项目或默认脑库。
在仓库根目录执行，替换 EXE 路径；输出目录必须尚不存在：

```powershell
python .\tools\acceptance\run_memory_tasks.py --binary 'C:\Qbrain\qbrain.exe' --host claude --output .\evaluation-001
python .\tools\acceptance\check_memory_task_run.py --directory .\evaluation-001 --binary 'C:\Qbrain\qbrain.exe' --report .\evaluation-001-readback.json
```

Codex 事件格式另用 --host codex 和新的输出目录。工具会清除子进程中的 QBRAIN、
OPENAI、ANTHROPIC 配置环境变量，并使用独立临时目录。临时脑库结束时清理，原始
合成输入、输出、诊断、哈希和执行记录保留到指定目录；失败会保留失败记录。
运行可执行文件本身仍须可信：这不是任意未知二进制的安全沙箱。

engine-report.json 的 ENGINE_PASS 仅表示 50 项引擎场景通过。model_answers 与
host_consumption 仍为 NOT_RUN，用量和费用仍为 null。执行耗时只描述这次合成
小语料，不能用作真实客户端延迟或规模性能保证。

## 后续真实模型对照的文件分离

with-context.json 提供实际返回的上下文；without-context.json 是相同问题、没有
上下文的对照。evaluator-key.DO-NOT-SEND-TO-MODEL.json 仅供评分器使用，不能交给
回答模型，也不能把整个评测目录挂载给有文件访问权限的回答 Agent。commands 目录
和其他条件下的答案也应保持隔离。公开 CI 样本可用于调试，正式对照应重新生成，
不能把已经看过答案的样本称为盲测。

目前工具不会自动启动模型。后续对照应使用同一模型版本和设置，分别在互不共享
历史的任务执行中提供 instructions 和该题 task；不得让其他题目或另一条件的答案
进入同一会话。必须另存实际模型/客户端版本、配置、请求响应及供应商计量证据。
单纯提交一份 answers 文件不能证明这些条件已满足。

把真实回答汇总进复制出来的 answers-template-with-context.json 或相应无上下文
模板，保留原模板和原任务包字节不变。每题对象仅有四个字段：case_id、state、values、
fact_ids。state 为 known、unknown、conflict 或 insufficient；values 是原话中的
QBN47Q_标记集合，fact_ids 是完整支持事实 ID 集合，不能重复。缺答允许保留未填，
但会计入所有 50 项的分母而不是删除。

示例只展示字段形状，不是可提交的真实回答：

```json
{"case_id":"preference-01","state":"known","values":["<实际标记>"],"fact_ids":["<实际64位事实ID>"]}
```

未知和预算不足的两个数组均为空，但 state 不相同。明确记录的未解决冲突须返回
两侧值和支持事实，不能猜一个赢家。用量没有供应商数据时保留 usage:null；禁止
把中文字数除以四当成实际 token 数。可提供的 usage 仅接收 source=provider_reported、
input_tokens、output_tokens、cost_usd，后三项分别允许 null，但评分器不会认证来源。

```powershell
python .\tools\acceptance\score_memory_tasks.py --key .\evaluation-001\evaluator-key.DO-NOT-SEND-TO-MODEL.json --packet .\evaluation-001\with-context.json --answers .\answers-with-context.json --report .\score-with-context.json
```

无上下文条件使用它自己的 packet 和 answers，不混用两种哈希。score 命令退出 0
表示完整合法的回答文件已评分，不表示全对；退出 1 表示合法但缺题，仍保存完整
分母的评分；退出 2 表示输入被拒绝或目标报告已存在。报告永不覆盖旧文件。

## 必须同时查看的两个指标

accuracy / packet_grounded_response：50 项中，是否正确依据该题提供的资料作答。
无资料时正确回答不知道也计为正确；所以这个指标不能单独解释记忆系统的收益。

answerable_resolution：在两种条件共同的 25 项 known/conflict 任务里，是否实际给出
正确状态、全部值和证据 ID。无上下文条件全答不知道，可有很高的第一项指标，但
这 25 项的解决率仍是 0。其他 25 项是拒答/遗忘/隔离/预算控制，不放进该解决率分母。

软件单元测试用标准答案夹具证明这一区别，夹具满分不是模型满分。所有评分始终
标记 host_consumption_verified=false、evidence_authenticity_verified=false、
usage_verified=false、general_answer_quality_verified=false。离线文件校验只能证明
文件间一致性，不能认证客户端确实运行、供应商收费或自然语言答案的整体质量。

## 当前版本与未完成项

N47Q 不更改 C++、数据库、安装器或默认采集开关，不发布新程序包。既有 N47O
公开包仍不含 N47P 的安装修复；评测使用其固定 EXE，不使用旧安装器接入用户机器。
历史 Claude 实机验收按原产品/操作系统范围保留，不能用本工具的两种事件格式
重放宣称新的 Claude/Codex 登录验收。真实模型 A/B、真实宿主消费、费用、规模和
更广泛语义任务仍需另行执行，属于 v1 尚未完成的验收。
