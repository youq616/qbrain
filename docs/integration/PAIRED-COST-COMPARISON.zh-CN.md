# N48I：配对任务费用对照

更新：2026-09-25。对应新增源码命令 `qbrain cost compare`，旧 N47X 公开安装包不含本命令。
应用仍为原生 C++20，不需要 Python 服务、Docker 或 WSL。Python 仅用于可选评测。

## 用途：把总费用对齐到同一组任务

N48F 计算单份规范化账本，N48G/N48H 将供应商响应转换为 `cost_input`。N48I 接收
两份这样的输入，核对共同任务、条件与调用归属，再比较总费用、每个任务、各阶段和
共享开销。它不发起模型请求，不读密钥，不打开脑库，也不自动采集遗漏的调用。

**费用可比不等于答案质量相同。** 失败任务可能更便宜；本模块仍会计入其已知费用，
但始终输出 `quality_verified=false`。真实评估必须另行检查正确率、缺答与失败率，
不能把负差额直接称为“保持质量的节省”。原 N47S 的执行许可与离线评分没有被修改，
本命令也不是自动读取 N47S `run.json` 的适配器。

## Windows 使用

从当前源码构建后，在仓库根目录的 **命令提示符 cmd.exe** 执行（不是 PowerShell）：

```bat
build\cl\qbrain.exe cost compare < examples\cost\compare-basic.json > comparison.json
echo %ERRORLEVEL%
```

PowerShell 5.1/7 可复用现有 UTF-8 桥脚本处理小示例：

```powershell
$ErrorActionPreference = 'Stop'
$exe = (Resolve-Path '.\build\cl\qbrain.exe').ProviderPath
$file = (Resolve-Path '.\examples\cost\compare-basic.json').ProviderPath
$utf8 = New-Object System.Text.UTF8Encoding($false, $true)
$inputJson = [System.IO.File]::ReadAllText($file, $utf8)
$result = & .\scripts\Invoke-QbrainJson.ps1 -FilePath $exe -ArgumentList @('cost', 'compare') -InputJson $inputJson
if ($result.ExitCode -ne 0) { throw $result.Stdout }
$result.Stdout | ConvertFrom-Json
```

桥脚本自身输入上限为 256 KiB，比本命令的 1 MiB 小；本轮没有改桥脚本或超时。
较大输入用 cmd.exe 的文件重定向，避免 PowerShell 管道编码差异。这里的 shell
示例是使用说明，并未在用户本机执行；原生命令的 CI 验证范围见结果审核。

退出码 0 表示产生合法报告，**仍可能 `comparison_eligible=false`**。退出码 2
表示输入/边界错误，只输出结构化错误码，没有部分费用报告。文件存在不代表成功。

## 输入契约

根对象恰有 `schema`、`comparison_id`、`currency`、`baseline`、`candidate`；schema
为 `qbrain-cost-comparison-v1`。两组各有以下字段，不接受未定义字段：

| 字段 | 要求 |
| --- | --- |
| `label` | 两组不同的标识，例如 `without-context` / `with-context`。 |
| `conditions_sha256` | 相同的 64 位小写十六进制摘要，标识声明的共同模型设置、资料版本、评测规则等。 |
| `ledger_complete` | 必须为 JSON 布尔值；表示调用方是否声明账本覆盖完整，不接受整数 0/1。 |
| `cost_input` | 原 N48F 输入对象：schema/currency/rates/calls，币种必须与根对象一致。 |
| `tasks` | 1–128 个任务，每项恰有 task_id/task_sha256/call_ids。 |
| `shared_call_ids` | 本组共享辅助调用 ID 列表，可为空。 |

ID 使用既有规则：1–64 字节，仅 ASCII 字母、数字、下划线、连字符、点、冒号。
完整可执行结构见仓库中的 `examples/cost/compare-*.json`，不需要猜测字段。
这些示例的摘要、模型和价格是合成值，**不是供应商报价或实际账单**。

任务摘要应绑定双方共有的问题、资料快照与任务版本，不要对有/无记忆的两个不同
请求正文直接分别求摘要后拿来配对。共同条件摘要排除的只能是明确设计的实验处理。
若故意改变主模型或主费率，本模块不会把这种价格差解释为同模型上下文优化。

这些摘要只检查**声明一致性**，不会读取原文件验证，也不能认证供应商内部模型、
采样状态或实际请求。`conditions_authenticated` 始终 false。

## 与现有导入模块衔接

将 N48G `cost import` 或 N48H `cost import-stream` 输出中的 **`cost_input` 对象**
放入相应组；不是把整份导入报告或 `cost_report` 作为输入。本模块重新计算金额，
不相信外部提供的总费用。两组可使用相同的 call_id，命名空间彼此独立。

每个 task 的 `call_ids` 必须非空，并至少包含一个 `stage=main` 调用；该任务的
embedding、summary、extraction、rerank 等辅助调用可以一起归入它。跨任务共享的
辅助调用放在 `shared_call_ids`，不能把 main 调用隐藏在共享列表。

**每条已提交调用必须恰好归属一次。** 少引用、引用不存在、重复引用、重复任务、
任务集合或任务摘要不一致，都拒绝；共享开销始终算入本组总费用，不按任务偷偷摊薄
或丢弃。每任务差额不包含共享开销，因此最终判断应看总 `change`，不能只看任务行。

失败、重试和未知结果标签保留原编号和用量，不自动去重删除。未取得用量的尝试应
由调用方显式记录为未知，并声明覆盖是否完整；不要省略它来制造完整账本。
漏掉一个整个任务或一条从未提交的调用，程序未必能知道，所以
`all_provider_calls_observed=false`，`ledger_complete` 不是独立遥测证明。
费用报告也不验证同一供应商响应是否被调用方改名重复提交。

## 何时计算差额，何时留空

任务集合、任务摘要、共同条件、币种矛盾属于输入错误，整批拒绝。
在输入结构合法的情况下，下列任一情况会使所有总额、任务、阶段及共享差额留空：

| 原因代码 | 含义 |
| --- | --- |
| `declared_coverage_incomplete` | 至少一组声明调用覆盖不完整。 |
| `cost_components_unknown` | 至少一个用量或所需费率未知。 |
| `primary_model_unknown_or_multiple` | 主调用的费率卡缺失，或某组声明了多个主模型。 |
| `primary_model_mismatch` | 两组声明的主 provider/model 不同。 |
| `primary_price_schedule_mismatch` | 两组主价格表不同，或主调用采用多种价格表。 |

费率卡 ID 可以不同，只要主 provider/model 和规范化主价格表相同。辅助模型、
辅助费率允许不同，相关费用必须全部提交并纳入总额。未使用的费率卡不被当作主模型。

未知不能默认为零，也不选择完整任务子集单独报告节省。继承 N48F 的一个区别：
**已知 0 Token** 即使费率未知，费用也为 0；**Token 未知**即使费率为 0，仍保持未知。
若所有用量都是 0 但主费率卡不存在，费用可能已知为 0，模型身份仍不足以通过对照。

## 输出与金额解释

`candidate_minus_baseline` = 候选总费用 − 基准总费用。负数表示提交账本中候选费用
较低，正数表示较高。金额为同币种精确字符串，保留 12 位小数；不使用浮点计价。
`relative_change` 为相对基准费用的精确约分分数，例如 `{"numerator":"-5","denominator":"12"}`。
它是比例，不是百分数；展示百分数时再做显示层换算，不改变底层计价。

基准费用为 0 时差额仍可计算，但比率为 null，原因为 `zero_baseline`。不能显示为
“无限节省”或除以零。超出无符号 64 位精确金额范围时返回 `cost_overflow`，不回绕。

输出含两组原始精确费用报告、按任务/阶段/共享拆分，以及排序后的绑定清单和摘要。
任务/调用/费率数组换序不改变规范化结果；重新分配调用或改变声明会改变绑定摘要。
规范化摘要不是对调用方或供应商身份的签名。

## 已执行的合成示例

| 示例 | 预期总差额（USD） |
| --- | --- |
| `compare-basic.json` | `-0.000050000000`，比例 `-5/12`。 |
| `compare-shared-overhead.json` | `+0.000010000000`；主调用虽便宜，共享开销使总费用增加。 |
| `compare-failed-retry.json` | `+0.000070000000`；在上一例继续计入失败重试。 |
| `compare-unknown.json` | null；缓存读取未知，不宣称总费用节省。 |
| `compare-rejected-task.json` | 退出 2，`comparison_task_mismatch`，无部分报告。 |
| `compare-zero-baseline.json` | `+0.000001000000`，比率 null。 |

这些文件已用新鲜完整 Linux 程序执行并保留输入/输出摘要；它们不是实际模型任务。
价格卡固定为合成的每百万 Token 1 USD，仅为演示整数和分数运算。

## 大小、安全及未完成边界

输入最多 1,048,576 字节，JSON 深度 32；每份账本序列化后不超过 262,144 字节，
最多 64 张费率卡、512 次调用、128 个任务；输出最多 8,388,608 字节。
重复 JSON 键、浮点 Token、布尔 Token、非法 UTF-8、未知字段等拒绝。
输出不包含请求/响应正文，但调用方 ID/模型名等并非自动匿名；不要填入密钥或私人内容。

本模块不含税、折扣、工具费、非 Token 费用、汇率换算或账单认证，也不证明召回
质量、客户端实际消费或所有请求都被看到。真实验证仍需授权环境，原 N47X 公开资产、
Issue40、PG 与签名均没有因这个计算模块通过而完成。

另已实际执行三次命令的合成衔接检查：两份 Chat 流分别经 `cost import-stream` 导入，
将所得 `cost_input` 原样嵌入对照；两份重算费用报告与导入结果完全相同，差额
`-0.000010000000 USD`、比例 `-10/133`。这证明该接口衔接可运行，不认证真实账单。
