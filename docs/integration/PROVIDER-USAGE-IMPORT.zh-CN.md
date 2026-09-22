# 供应商用量导入与精确 Token 费用核算（N48G）

原生 `qbrain cost import` 从标准输入读取已经取得的供应商响应，将其转换为四个
互斥用量桶，再调用原 N48F 精确计价算法。完整输出同时包含规范化输入、逐项映射
和费用报告。它不联网、不查价格、不读取密钥、不打开脑库，也不自动采集请求。
需要含 N48G 的源码构建；当前 N47X 公开包不含 cost import 或 cost report。

## 输入：明确格式、调用身份和费率

顶层只允许 schema、currency、rates、records。schema 为 qbrain-usage-import-v1；
currency 为三个大写字母标签，rates 沿用[规范化计价定义](TOKEN-COST.zh-CN.md)，
最多64份。每份卡片明确 provider、model 和四桶 per_million 十进制字符串费率，
未知价格使用 null，不以 JSON 浮点数或猜测值代替。

records 最多128条，每条恰好包含 call_id、stage、rate_id、attempt、outcome、format、
response。stage 为 main、embedding、summary、extraction、rerank 或 other；attempt
为1–100；outcome 为 success、failure 或 unknown。call_id 标识一次实际尝试，
不是提示词。rate_id 选择调用方已确认适用的卡片，不自动匹配当前型号或价格档位。

| format | 接受的对象及用量口径 |
| --- | --- |
| openai_chat | 最终 chat.completion 对象，choices 已有 finish_reason；从总输入中扣除已知缓存读写 |
| openai_responses | 最终 response 对象，状态为 completed/failed/incomplete/cancelled；成功标签只可用于 completed |
| anthropic_messages | assistant message 且 stop_reason 非空；普通输入、缓存读取和创建已是分列计数 |

只支持这里明确列出的文本 Token 合约，不是任意兼容网关或所有历史版本的自动适配。
流式片段、未结束响应和无法解释的明细拒绝。response=null 只能用于 failure/unknown
尝试；没有观察到用量时保留未知。失败尝试若有有效用量，仍正常计价，不推定重试免费。

## 已执行的合成示例

[三种格式的完整合成输入](../../examples/cost/import-three-providers.synthetic.json)使用
虚构模型、响应和费率，不是供应商报价。在源码根目录、已有新构建的情况下运行：

```powershell
$ErrorActionPreference = 'Stop'
$exe = (Resolve-Path '.\build\cl\qbrain.exe').Path
$path = (Resolve-Path '.\examples\cost\import-three-providers.synthetic.json').Path
$json = [IO.File]::ReadAllText($path, [Text.Encoding]::UTF8)
$r = & '.\scripts\Invoke-QbrainJson.ps1' -FilePath $exe -ArgumentList @('cost','import') -InputJson $json
if ($r.ExitCode -ne 0) { throw $r.Stdout }
$imported = $r.Stdout | ConvertFrom-Json
$imported.cost_report | ConvertTo-Json -Depth 20
```

该输入已用实际 Linux 程序执行，总计应为 **0.000729000000 USD**。每条普通输入50、
缓存读取30、缓存创建20、输出50；输出中的推理细分不再额外相加。上面新增的说明
命令按接口复核，不冒称又执行了一轮用户 Windows 安装或 PowerShell 文档测试。

cost_input 可原样交给 cost report，结果应等于导入输出中的 cost_report：

```powershell
$normalized = $imported.cost_input | ConvertTo-Json -Depth 20 -Compress
$r = & '.\scripts\Invoke-QbrainJson.ps1' -FilePath $exe -ArgumentList @('cost','report') -InputJson $normalized
if ($r.ExitCode -ne 0) { throw $r.Stdout }
$r.Stdout
```

导入器总输入上限1048576字节，单个响应序列化后最多262144字节；规范化输入仍受
N48F 的262144字节上限约束，完整输出最多2097152字节。现有 PowerShell 字节桥的
输入上限也是262144字节，因此上例桥接方式只适用于该范围内的输入，不会让字节桥
自动扩大到导入器上限。不要绕过检查或把大文件截断后当成完整响应。

## 未知、零值和重复不是同一件事

缺字段与 null 均保留为未知，不能补0只为得到 complete=true。明确总输入为0时，
可以证明对应 OpenAI 缓存读写也为0；其他情况下只做已知子集扣除，不猜测剩余值。
旧响应没有 cache_write_tokens 时，可能产生不完整报告，这是明确边界而非免费缓存。

同一输入内不允许重复 call_id，也不允许同一供应商响应身份换一个调用 ID 再收费。
去重不跨独立命令调用持久化；调用方仍负责实际采集、重试关联和跨批次去重。
混合正数5分钟/1小时缓存写入不能用一个虚构均价表示，模块会拒绝。正数音频或非空
逐迭代明细等未支持计费形状同样拒绝，不悄悄漏计。服务端工具调用费不纳入 Token 金额。

## 输出、隐私和错误

cost_input 是规范化记录，cost_report 是原精确计价结果，mapping 说明每次映射、
供应商响应身份摘要和未知／排除项。金额以12位小数字符串输出，不使用二进制浮点
累积；存在未知数量或价格时，完整总额为 null，同时保留已知小计。

命令退出0只表示输入处理成功，不代表用量完整、金额完整或账单已认证。检查
usage_complete、cost_report.summary 中的 complete 与 unknown_components；不要只检查退出码。
原始响应正文不会复制进输出或规范化摘要，修改忽略正文不改变费用；但调用ID、
模型／费率标签等调用方元数据仍可出现在输出，不能把它视为任意输入的自动匿名化。

拒绝退出码为2，返回固定 usage_* 或继承的 cost_* 错误码，整份输入不输出部分成功。
重复键即使位于忽略的正文对象内也拒绝。数量矛盾、错误类型、型号／卡片不匹配、
重复响应、超限等应先核对输入来源，不能自动改数值后继续。不会访问或修复用户数据库。

费用完整仅指已提供 Token 记录可按所给卡片计算。来源真实性、调用是否全部采齐、
费率日期／档位／TTL适用性、工具费用、税费、折扣和最终账单舍入仍须独立核验。
本模块不证明费用节省、真实模型记忆消费或 Issue40 的历史原因。

[完整工程审核](../nodes/N48G-HARD-AUDIT.md) · [精确证据](../nodes/n48g-evidence/SUMMARY.json)。
