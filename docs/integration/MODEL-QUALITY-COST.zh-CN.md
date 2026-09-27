# N48L：同次运行的逐题质量与主请求费用联合评估

更新：2026-09-27。可选离线工具 `tools/acceptance/model_evaluation.py export|verify`。
应用仍为 Windows 原生 C++20；Python 仅用于这个评测工具，不是常驻服务。

## 作用与边界

将同一份 N47S 执行目录里的原始回答、独立评分答案文件和显式费率卡，连接到原
N47Q/N47S 评分与 N48J/N48I 原生费用计算。不能拿一份质量汇总和另一份费用汇总
直接拼接：评分使用的响应快照必须与费用来源清单完全一致，输出前还复查源文件、
答案文件、价格与程序字节。已有原生计价、评分及执行授权均不改变。

这是固定 50 个记忆任务、有/无上下文共 100 次计划请求的离线评测器，不是通用
大模型评委。不会联网、发起付费请求、修改脑库或安装客户端。答案文件只用于
离线评分，不传给计价程序或模型，也不复制到报告里。

**范围只包括计划内主请求（scheduled_main_requests_only）。** Embedding、摘要、
提取、资料准备等计划外费用不在其中。费用降低不自动表示全流程节省，更不证明
真实模型、实际客户端或未测试任务的质量提升。

## 两个不能混用的指标

| 指标 | 固定分母及含义 |
| --- | --- |
| `packet_grounded` | 每组 50 题。回答是否符合该题提供的上下文与结构化回答规则；无证据时正确拒答也可以得分。 |
| `answerable_resolution` | 每组 25 道预先确定可解的题。是否给出了与答案文件一致的状态、完整值集合和支持证据 ID 集合。 |

无上下文组可能得到 **50/50 的依据上下文正确率，却只解决 0/25 道题**。这是恰当
拒答，不等于已经解决全部问题。冲突题要覆盖完整冲突值及证据，数组顺序不重要，
漏值、错误值或错误证据不能按正确解决计数。失败和未执行的位置留在固定分母里。

报告列出全部 50 道题的前后状态，并分别统计改善、退步、两边正确和两边不正确。
一题变好不能抵消另一题变差；总分相同也可能存在真实的逐题退步。

## 联合判定的含义

只有 100 个响应完整、费用可比，才计算本批样本上的逐题质量/主请求成本关系。
结果是描述性关系，不是显著性检验，也不是总体质量不劣的统计结论。

| `decision.result` | 含义 |
| --- | --- |
| `CANDIDATE_DOMINATES_OBSERVED_CASES` | 候选在每一道题的两个适用质量维度都不退步，主请求总费用不增加，并且至少一项质量改善或费用严格下降。 |
| `BASELINE_DOMINATES_OBSERVED_CASES` | 相反方向上，基准方案在已观察维度里不劣且至少一项严格更好。 |
| `TRADEOFF_OBSERVED` | 质量与费用之间、或不同题目之间存在取舍，不能直接宣布候选更优。 |
| `NO_CHANGE_OBSERVED` | 本批所有已评分维度和主请求总费用均无变化。 |
| `NOT_COMPARABLE` | 响应不完整、存在未尝试位置、费用未知或主模型/费率不满足原生对照条件。保留计数，但不给联合优劣结论。 |

两个方案都答错同一批题时，其中一个更便宜，仍可能在这些**已观察维度**上占优。
因此必须同时查看绝对解决率，不能只看判定名称；0 道解决题不会被包装成“有效方案”。
`quality_preserving_savings_verified` 等真实效果认证标记始终为 false。

`cost_per_resolved_task` 的分子是该组全部已纳入的主请求费用，而不是只挑成功题
对应费用；分母是已解决任务数。值为精确约分分数，币种单独标注。解决 0 题时为
null，原因为 `zero_resolved_tasks`；不可比时同样留空，不报告免费或无穷值。
原评分文件里的既有小数准确率保留原样；新的差额、比率不使用浮点近似计价。

## Windows 使用

准备已有 N47S 运行目录、与该运行绑定的离线答案文件、N48J 费率卡和可信 Qbrain
程序。N48K Windows 包已有所需原生计价命令，但其固定 ZIP **没有新增 N48L 脚本**；
从本轮源码/工具包取脚本，不覆盖旧包或已有证据。完整工具依赖为同版本的五个文件：
`model_evaluation.py`、`model_cost.py`、`model_ab.py`、`memory_task_contract.py`、
`run_memory_tasks.py`，应放在同一目录。

以下以源码仓库根目录为例。修改实际路径，输出目录自身必须不存在，父目录须存在。
不要把答案文件或输出目录放入被严格核验的 `--run` 目录内。

```powershell
$ErrorActionPreference = 'Stop'
$exe = (Resolve-Path 'D:\Qbrain\qbrain.exe').ProviderPath
$run = (Resolve-Path '.\model-run-new').ProviderPath
$key = (Resolve-Path '.\tasks\evaluator-key.DO-NOT-SEND-TO-MODEL.json').ProviderPath
$rates = (Resolve-Path '.\model-rates.json').ProviderPath
$out = Join-Path (Get-Location).Path 'evaluation-new'
python .\tools\acceptance\model_evaluation.py export --run $run --key $key --rates $rates --binary $exe --output $out
if ($LASTEXITCODE -ne 0) { throw 'Evaluation rejected; preserve original evidence.' }
python .\tools\acceptance\model_evaluation.py verify --run $run --key $key --rates $rates --binary $exe --output $out
if ($LASTEXITCODE -ne 0) { throw 'Evaluation readback failed.' }
Get-Content -Raw -LiteralPath (Join-Path $out 'evaluation.json') | ConvertFrom-Json
```

命令不会重新执行模型。不要通过盲目重发请求解决记录缺失，否则可能再次计费。
退出 0 表示导出/复核成功，仍可能是 `NOT_COMPARABLE`；输入/本地错误退出 2。
该 PowerShell 示例没有在用户本机执行。Windows CI 执行的是相同工具的原生子进程
调用与实际回环请求链路，不应表述为已登录客户端验收。

## 六个输出文件

`evaluation.json` 是逐题结果、计数、精确指标和联合判定。`quality-scores.json` 保留
原评分结果；`cost-analysis.json` 保留原费用桥接结果；`comparison-input.json` 是
原生对照输入，覆盖不足时为 null。`provenance.json` 绑定源文件、答案摘要、费率、
程序和工具版本；`MANIFEST.json` 最后写入，列出前五个文件的大小及摘要。

`verify` 从原始输入重新计算并逐字节比较，不仅验证可被重写的输出清单。修改计数、
金额或优劣判定后同步修改摘要仍会失败。磁盘错误可能留下不完整目录，该目录不能
算验收完成，不会自动删除或覆盖。程序/脚本/原始资料有改变时应导出新目录。

源文件、答案、费率和程序都必须是可信的普通文件；沿用 N48J 的大小、深度、重复
JSON 键、链接/reparse 和源数据复查规则。答案文件上限 8 MiB，每份输出上限 8 MiB；
更细的运行目录与计价限制沿用已有模块。并发检查不是恶意文件系统或任意 EXE 沙箱。

## 已执行的合成例子

| 情形 | 正确解释 |
| --- | --- |
| 无上下文 50/50、解决 0/25；候选 50/50、解决 25/25，费用相同 | 候选在本批维度上占优；不是“两个方案效果完全相同”。 |
| 候选便宜但只拒答，解决率仍为 0 | 有逐题质量退步时为取舍，不能称为效果提升。 |
| 一题改善、另一题变差，总分相同 | 显示退步，不能用净分数抵消。 |
| 候选解决更多，但总费用更高 | 显示质量/费用取舍。 |
| 只有 1、2、49、50、99 或 100 次请求尝试后出现失败 | 固定分母保留，失败不删除；不给完整优劣结论。 |

上述是离线合成记录及参考响应器产生的实际测试输入，不是真实模型推理。两个方案
的回答状态/值/证据按原评分语义比较，而不是评估自由文本质量。答案文件和供应商
来源未认证，价格适用性需自行核实。真实客户端消费、代表性真实模型实验、全流程
成本、PG、签名、稳定版和 Issue40 的验收不因此完成。
