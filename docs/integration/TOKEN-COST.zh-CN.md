# 全链路规范化 Token 费用核算（N48F）

原生 `qbrain cost report` 从标准输入读取一份规范化 JSON，按提供的用量与费率生成
逐调用、逐阶段、逐费率卡和总计报告。它不访问脑库、不联网搜价、不读取供应商
密钥、不调用模型，也不自动采集请求。目前需要含 N48F 的源码构建，旧 N47X 包不含它。

## 输入定义

schema 必须为 qbrain-cost-input-v1，currency 为三个大写字母的币种标签。同一报告
仅一个币种，不换汇、不核对正式币种清单。rates 最多64份，calls 最多512条；输入
最多262144字节，输出最多2097152字节。标识符1–64字符，只允许ASCII字母、数字、
下划线、短横线、点和冒号，不接受提示词、正文或额外字段。

每份费率卡包含 rate_id、provider、model 和 per_million。所有费率均是“每百万
Token 的币种金额”，用十进制字符串或 null 表示，最多6位小数、范围0–1000000。
不使用JSON浮点数、指数写法、符号、空白或多余前导零。例如用 "2.5"，不用2.5。
费率由调用方核实并提供，可用不同 rate_id 区分不同调用的版本、档位和日期。

每条调用包含 call_id、stage、rate_id、attempt、outcome 和 tokens。
stage 为 main、embedding、summary、extraction、rerank 或 other；attempt 为1–100；
outcome 为 success、failure 或 unknown。调用ID和费率卡ID分别不得重复。失败请求
若返回用量仍照算；每次真正尝试须有自己的调用ID，程序不会猜测哪些重试免费。

四个 Token 桶必须全部出现，且互不重叠：

| 字段 | 含义 |
| --- | --- |
| input_uncached | 未计入缓存读/写的普通输入 |
| input_cache_read | 命中缓存并按缓存读取价格计费的输入 |
| input_cache_write | 按缓存创建价格计费的输入 |
| output | 按输出价格计费的Token |

Token 数为0–1000000000的整数或 null，不接受布尔值、浮点数或字符串。不要直接把
供应商的“总输入”再加一次缓存用量。同一次调用的同一桶有不同TTL/阶梯价而无法
无损表示时，保留该桶费率为null；不要取未经证明的均价，也不要凭空增造调用次数。
该模块不是供应商原始 usage 或分层价格的适配器。

## 可复制的离线示例

仓库中提供 [完整合成输入](examples/token-cost-synthetic.json)，包含失败首尝试、
成功重试和一次抽取调用，费率仅用于演示，不是任何真实供应商报价。
在源码根目录、已有新构建时，用现有UTF-8字节桥运行：

```powershell
$ErrorActionPreference = 'Stop'
$exe = (Resolve-Path '.\build\cl\qbrain.exe').Path
$json = [IO.File]::ReadAllText((Resolve-Path '.\docs\integration\examples\token-cost-synthetic.json').Path, [Text.Encoding]::UTF8)
$r = & '.\scripts\Invoke-QbrainJson.ps1' -FilePath $exe -ArgumentList @('cost','report') -InputJson $json
if ($r.ExitCode -ne 0) { throw $r.Stdout }
$r.Stdout
```

示例总计为0.003660000000，其中失败首尝试0.000200000000、成功重试0.003160000000、
抽取0.000300000000。Linux实际程序已核对示例；上面的命令文字不冒称用户本机执行。
不要加 --brain、供应商密钥或价格查询参数，cost 入口不打开默认脑库。

## 已知小计不等于完整总额

每个桶输出 tokens、rate_per_million、cost 和 missing。缺少用量时 missing=usage_unknown；
有正用量但缺价时为 rate_unknown 或 rate_card_missing。存在未知项时 complete=false，
total_estimate=null，同时保留 known_subtotal 与 unknown_components。按阶段和费率
分组遵循相同规则，不把未知当成零。

已知0 Token 即使缺价也确定花费0；未知 Token 即使费率为0仍保留未知。空calls总额
为0只表示没有提交记录，不代表观察到了全部请求。retry_calls 是 attempt>1的记录数，
不是自动重建出的重试链；failed_calls 和 unknown_outcome_calls 不影响用量是否计价。

所有金额按12位十进制字符串输出，输入费率规范化为6位。固定整数计算不会产生
二进制浮点累积误差，但有明确范围：所有已知费用之和最大18446744.073709551615。
超过则整份报告拒绝 cost_overflow，不输出一个已经截断的成功小计。可在业务上按
独立批次核算，不能把跨批次累计超界当作本模块已支持无限总额。

input_sha256 绑定规范化输入。调用、费率卡重排和等价费率尾零不会改变报告；用量、
标识、结果、尝试次数及卡片内容改变则会改变摘要。摘要不是签名或来源认证。

## 输出与错误边界

成功退出码0，拒绝退出码2；错误只输出固定cost_*代码。常见错误为 cost_fields、
cost_duplicate_key、cost_duplicate_call、cost_duplicate_rate、cost_quantity、
cost_rate_decimal、cost_rate_range、cost_input_limit 和 cost_overflow。参数/解析/汇总
全部完成后才生成成功输出，不会先输出部分可计价调用再报告后面失败。

complete=true 只指提交的Token项可以计价。billing_verified、all_provider_calls_observed、
fees_taxes_discounts_included、currency_conversion_performed 均为false。
税费、非Token工具费用、折扣、汇率和供应商最终账单的舍入规则不包含。没有实测
费用节省，也没有自动把本地历史日志变成已经认证的供应商用量。用户提供的ID仍会
出现在报告中，报告不是对任意输入的自动脱敏。需要真实费用验收时应保留实际用量
来源及适用费率的独立证据，不能只依据本报告的算术完整标志。

[完整审核](../nodes/N48F-HARD-AUDIT.md) · [精确证据](../nodes/n48f-evidence/SUMMARY.json)。
