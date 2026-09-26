# N48J：模型 A/B 执行记录直接生成费用报告

2026-09-26。新增可选评测工具 `tools/acceptance/model_cost.py`，接续已有 N47S
模型执行目录与 N48G/N48F/N48I 原生计价功能。应用本身仍是 Windows 原生 C++20，
没有引入 Python 常驻服务、Docker 或 WSL 要求。

## 解决的问题与明确范围

以前已有“执行模型对照”和“对照两份费用账本”，但需要人工从执行目录整理用量、
配对任务和费用输入。本工具从一个既有 N47S 运行目录完成这段衔接。它不执行模型，
不读 API 密钥，不读评分答案，不访问脑库，不自动采集其他请求。

**本报告只覆盖计划内的主模型请求：`scheduled_main_requests_only`。**
资料准备、Embedding、摘要、提取、重排等计划外开销不在本工具的观察范围；
报告始终保留 `full_pipeline_costs_included=false`。负费用差额不能解释为全流程
节省，更不能代表保持答案质量。原 N47S 的独立评分和真实客户端验收仍然需要保留。

输入限定为 N47S `qbrain-model-plan-v2` 与 `qbrain-model-run-v1`：固定 50 个任务、
有/无上下文共 100 个计划请求。它不是任意供应商日志读取器、聊天导出工具或通用
SSE 导入器。完整 SSE 仍使用 N48H `cost import-stream`。

## 使用前准备

使用包含 N48J 的源码及至少包含 N48I 的可信 `qbrain.exe`。公开 N47X 安装包不含
后续原生计价命令，不能拿它运行本流程。Python 只用于这个可选评测工具。

`--run` 指向已有 N47S 执行目录，根目录应只有 `plan.json`、`run.json` 和已经尝试的
编号目录（`001` 等）。不要把评测的答案密钥、备注或新增文件放进去。工具要求严格
清单并验证原始字节，不在原目录中写入或修复记录。

另行创建费率 JSON，格式如下。仓库 `examples/cost/model-execution-rates.synthetic.json`
是同结构的**虚构算例，不是报价，不可直接用于真实账单**：

```json
{
  "schema": "qbrain-model-cost-rates-v1",
  "scope": "scheduled_main_requests_only",
  "currency": "USD",
  "rates": [{
    "rate_id": "main-price",
    "provider": "openai",
    "model": "fixture-model",
    "per_million": {
      "input_uncached": "1.234567",
      "input_cache_read": "0.123456",
      "input_cache_write": "2.000003",
      "output": "3.456789"
    }
  }]
}
```

`provider: openai` 表示此适配器所使用的 Chat Completions 用量格式，不认证实际商业
供应商。`model` 必须是保存响应中报告的准确型号；不能拿请求别名猜测返回的快照
型号。一个型号只能对应一张卡；支持列出多个返回型号，但同组多主模型仍可能被
原生对照器判为不可比。价格字符串为每百万 Token 的同币种价格，最多六位小数；
未知费率可为 `null`，不要填零代替未知。费率适用性由调用方核实。

## Windows 完整命令

在仓库根目录的 PowerShell 中，按实际位置修改前三个路径。输出目录的父目录必须
已存在，输出目录自身必须是新目录，且不能位于运行源目录里面：

```powershell
$ErrorActionPreference = 'Stop'
$exe = (Resolve-Path '.\build\cl\qbrain.exe').ProviderPath
$run = (Resolve-Path '.\model-run-new').ProviderPath
$rates = (Resolve-Path '.\model-rates.json').ProviderPath
$out = Join-Path (Get-Location) 'model-cost-new'
python .\tools\acceptance\model_cost.py export --run $run --rates $rates --binary $exe --output $out
if ($LASTEXITCODE -ne 0) { throw 'Cost export rejected. Preserve the original run; do not blindly retry model requests.' }
python .\tools\acceptance\model_cost.py verify --run $run --rates $rates --binary $exe --output $out
if ($LASTEXITCODE -ne 0) { throw 'Cost evidence readback failed.' }
Get-Content -Raw -LiteralPath (Join-Path $out 'analysis.json') | ConvertFrom-Json
```

以上只执行离线分析，不触发 N47S 的付费 `execute`，也不需要在这个命令中提供密钥。
不改变现有付费调用的批准要求。示例 PowerShell 块没有在用户本机执行；CI 的实际
跨平台测试范围见 N48J-HARD-AUDIT.md。

退出码 **0 表示报告导出或复核成功，不等于费用可比**。必须查看
`comparison_eligible`、`comparison`、`unattempted_requests` 和
`comparison.unavailable_reasons`。拒绝或本地 I/O 失败返回 2，错误消息不输出源路径、
提示词或响应正文。不以“目录已经存在”或“有个 JSON 文件”判断成功。

## 四个输出文件

| 文件 | 内容 |
| --- | --- |
| `analysis.json` | 两组规范化账本和精确金额、100 个计划位置的覆盖观察、可用时的费用对照；无提示词或答案正文。 |
| `comparison-input.json` | 可直接交给 N48I 的输入；存在未尝试位置时为 JSON `null`，不会伪造完整任务账本。 |
| `source-manifest.json` | 源文件相对名、长度与摘要，费率/程序/工具组件身份、明确的主请求范围；不保存绝对路径。 |
| `MANIFEST.json` | 前三个文件的大小与摘要，最后写入，作为本次输出完成的标记。 |

`verify` 并不是只读这个清单后宣布通过。它重新读取原始运行和费率，用给定可信
原生程序重新算出整份报告，再比较所有确定性字节及文件清单。修改金额后同步更新
输出清单也不能通过。改变程序字节、工具版本、源数据或费率后应导出新目录，不能
把旧输出当成同一次验证。没有对全部文件被协同伪造的来源认证能力。

## 处理失败、未知与未执行请求

| 源记录情况 | 处理 |
| --- | --- |
| 正常完整回答 | 核对原始请求、started/receipt、原响应摘要与解析结果；从原响应保留缓存等用量细节交给原生导入器。 |
| 回答格式错误但有完整终止响应 | 仍保留该失败尝试的可用用量和费用，不因答案错误免费处理。 |
| 网络失败、被脱敏或非终止/缺失响应 | 保留真实尝试，Token 未知；不填零，不沿用其他调用的用量。 |
| 未尝试的计划位置 | 只记录覆盖缺口，`call_id=null`；不创建虚构调用或费用。 |
| 少于 100 次尝试 | 输出已有部分账本、完整覆盖表，`comparison=null`，不只比较已完成的有利子集。 |
| 100 次都尝试但有失败 | 保留 50 个配对任务，通过不完整声明保守停止差额输出。 |
| 没有最终 `run.json` 的硬崩溃 | 拒绝自动导出；不猜测服务器是否已计费，不自动恢复或重发。 |

N47S 回执中的 `usage` 只保存输入/输出汇总，会丢失缓存细节。本模块使用核验后的
原始响应，不从汇总值反推互斥 Token 桶。原生导入器对于缓存未知、矛盾数量、
不支持的额外计费字段等仍按原契约处理；桥接不放宽规则，也不猜供应商默认值。

完整回答必须有可识别的 Chat `object` 与终止标记；不会给缺少它们的响应补上标签。
同一响应 ID 在两组之间重复也会拒绝。用于计价的是明确字段投影，不是完整响应
重建：输出不包含正文，但调用 ID、模型名、任务 ID 和内容摘要也不应当作自动匿名。

## 费用与效果分开理解

差额方向为“有上下文候选 − 无上下文基准”。两组共同条件和任务摘要绑定到同一份
计划及成对输入资料，并不认证模型实际实现、供应商费率或执行来源。
`LOOPBACK_TEST` 始终保留为回环测试，不能显示成真实模型或真实账单。

测试算例中输入减少会产生负差额；另一条实际引擎→回环链路中输入增加则产生
正差额。两种结果都只是合成响应的计价结果。错误回答同样可能便宜，因此不把费用
差额合并成“效果提升评分”，也不自动读取标准答案。

税费、折扣、非 Token 费用、汇率和账单认证均不在范围内；`billing_verified`、
`quality_verified`、`host_consumption_verified`、`all_provider_calls_observed` 始终为 false。

## 文件与运行边界

计划最多 8 MiB、运行索引 1 MiB；单个请求/started/receipt 64 KiB，单个保存响应
1 MiB，总源文件 128 MiB；价格文档 256 KiB，每个输出最多 8 MiB。JSON 额外检查
重复键、精确数值类型、Unicode、非有限数值及深度。原生计价仍执行自己的更细边界。

不接受符号链接、Windows reparse point 或非普通文件，并复查读前读后状态以及
发布前的源字节。严格清单不接受额外文件或未尝试位置的目录。输出只写新目录；
磁盘写入失败可能留下不完整目录，不报告成功，也不自动覆盖或删除它。

这些措施不等于对恶意并发文件系统或任意可执行文件的操作系统沙箱。
`--binary` 必须是可信 Qbrain。请保存原始运行、工具版本和费率，避免并行编辑它们。
本模块不替代真实客户端消费、真实模型质量/全流程费用、PG、签名和 Issue40 验收。
