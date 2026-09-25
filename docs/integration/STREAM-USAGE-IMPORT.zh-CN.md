# 完整 SSE 流的离线用量导入与计价（N48H）

更新：2026-09-25。本说明对应 N48H 整合候选源码，不是已发布的 Windows 安装包。
本次整合以远端修复提交 817d222a 为基线，保留其产品、原始测试和 543 用例审核，
加入此前独立开发的 711 用例与 47 项直接检查。N47X 公开包不含本命令。
候选的验收状态以 PR #49 与最终结果审核为准，不能用旧 EXE 代替当前源码。

## 用途与边界

`qbrain cost import-stream` 从标准输入读取一个 JSON 文档，其中保存完整的 SSE
响应字符串。它不发网络请求、不打开脑库、不读 API 密钥，也不自动采集会话。
它将三个明确支持的协议转换成互斥 Token 桶，并复用原有 `cost report` 精确计价。
成功输出是 `qbrain-stream-import-report-v1`；拒绝时退出码为 2，只返回结构化错误。

支持 `openai_chat`、`openai_responses` 和 `anthropic_messages`。这是严格的完整流
离线验收器，不是通用 EventSource 客户端，不接受断点续传片段，也不重建/验证正文。
已保存的流可能含私人正文，应由调用方妥善保管；不要上传真实会话或密钥到仓库。

## 输入格式

根对象必须只有 `schema`、`currency`、`rates`、`records`，其中 schema 为
`qbrain-stream-import-v1`。每条记录恰有以下字段：

| 字段 | 含义 |
| --- | --- |
| `call_id` | 本批次内唯一的调用 ID，不建议放私人信息。 |
| `stage` | 既有 N48F 阶段，例如 `main`。 |
| `rate_id` | 引用本输入的显式费率卡；provider/model 必须准确匹配。 |
| `attempt` / `outcome` | 尝试编号与既有结果标签；失败请求的已知用量仍计价。 |
| `format` | 上述三种协议之一，不自动猜测。 |
| `stream` | JSON 字符串内保存的完整 UTF-8 SSE 正文，不是文件名或 URL。 |

所有费率均由调用方核实适用性。仓库示例使用虚构模型与合成费率，不是供应商报价。
同批重复调用 ID 或重复响应身份会拒绝；没有跨批次持久化去重，重复导入不是自动
幂等写入。整个命令不写数据库，因此也不会在导入失败时留下一半已入库的数据。

## Windows 使用

在已构建当前候选源码的仓库根目录，用 PowerShell 5.1/7 处理小示例：

```powershell
$exe = (Resolve-Path '.\build\cl\qbrain.exe').ProviderPath
$file = (Resolve-Path '.\examples\cost\stream-openai_chat.json').ProviderPath
$utf8 = New-Object System.Text.UTF8Encoding($false, $true)
$inputJson = [System.IO.File]::ReadAllText($file, $utf8)
$result = & .\scripts\Invoke-QbrainJson.ps1 -FilePath $exe -ArgumentList @('cost', 'import-stream') -InputJson $inputJson
if ($result.ExitCode -ne 0) { throw $result.Stdout }
$result.Stdout | ConvertFrom-Json
```

复用的桥脚本自身上限是 **256 KiB**，小于本命令的 4 MiB 输入上限；本轮没有改动
桥脚本或其超时。较大输入可在 Windows 的 **命令提示符（cmd.exe，不是 PowerShell）**
使用原生文件重定向，避免经过 PowerShell 字符编码管道：

```bat
build\cl\qbrain.exe cost import-stream < input.json > report.json
echo %ERRORLEVEL%
```

程序成功退出码为 0；输入错误为 2。不要以“输出文件存在”判断成功，也不要将非零
退出码的错误 JSON 当作费用报告。本轮未执行上述 Windows shell 示例；Windows 原生命令验收范围另见最终审核。

## 已执行的合成示例

仓库 `examples/cost/` 下有五个 UTF-8 JSON 示例，已用新构建的完整 Linux 程序执行：

| 文件 | 预期 |
| --- | --- |
| `stream-openai_chat.json` | 完整 Chat 尾部用量，只计一次。 |
| `stream-openai_responses.json` | 只取终止响应的最终用量。 |
| `stream-anthropic_messages.json` | 起始输入保留，输出累计更新覆盖，不相加。 |
| `stream-unknown-cache.json` | 缓存分项未知；总估计为 null，不推定费用完整。 |
| `stream-rejected-truncated.json` | 缺少 `[DONE]`，返回 `stream_missing_terminal`。 |

前三例互斥 Token 桶均为未缓存输入 70、缓存读取 30、缓存写入 0、输出 20，按示例
费率计算为 `0.000133000000 USD`。未知缓存例只确定输出费用，已知小计为
`0.000060000000`，不表示全部费用只有这个数。这些是合成算例，不是实际账单。

## 三种协议如何取数

Chat 必须保持响应 ID/model 一致，所有 choice 结束，至多一个 `choices: []` 的用量
尾块，并以 `[DONE]` 结束。没有尾部用量但正确结束时，用量未知；不将文本块数量当
Token 数，更不将每个块重复计费。

Responses 要求从 `response.created` 开始，起始序号只允许 0 或 1，之后严格连续。
必须有且仅有 `response.completed`、`response.failed` 或 `response.incomplete` 之一
作为终止响应。只使用终止响应的用量，之前的数值只用于一致性检查。支持的正文事件
限于源码明确列出的文本、拒绝、函数调用和推理事件子集；音频等其他事件会拒绝。
序号规则不验证正文是否确实由该供应商生成。

Anthropic 要求 `message_start`、配对的内容块、累计 `message_delta` 和 `message_stop`。
更新中缺失字段表示没有新值；字段为 null 表示未知；整个 `usage: null` 会清空当前
用量，而不是继续沿用旧完整结果。初始 output_tokens 单独存在不能证明最终输出。
文本、thinking、redacted_thinking、tool_use 为明确支持的块类型；fallback 等不支持。

**历史数值不会因为后续 null 消失，但只能作为下界，不能填补未知最终用量。**
本轮修复了两种矛盾绕过：早期总量 100，末帧输入/输出合计 10 且总量缺失；早期缓存
写入 100，末帧缓存总量为 null 而 TTL 分项合计 10。两者现在整批拒绝，错误码为
`stream_usage_lower_bound`。相等或增加仍允许，真正缺失的数据仍为未知。

## 限制、错误与解释

每次最多 32 条流；JSON 输入最多 4,194,304 字节；单流最多 524,288 字节；单个事件
的 data 内容最多 262,144 字节；每流最多 4,096 个 data 事件。支持 CR/LF/CRLF、开头
BOM、注释和多行 data。最后一个事件必须完整终止；重复命名字段、未知 SSE 字段、
无效 UTF-8/NUL、重复 JSON 键、身份冲突、序号缺口、计数下降及终止后的 data 都拒绝。

`stream_contract_validated=true` 不等于 `response_content_validated=true`，也不等于
供应商认证、模型真实消费或所有请求都被观测。报告不输出响应正文或流正文哈希，但
调用 ID、模型名等调用方元数据并非自动匿名。既有响应身份引用哈希不是正文哈希。
音频计费、混合 TTL、非空 iterations 等继续遵守 N48G 的限制；工具费、税费、折扣、
币种转换和账单真实性不在本模块内。不得将未知计数或缺失费率擅自填成零。

## 开发验证入口

相对整合基线 817d222a，原有产品头文件、`.ci/test_stream_usage.py`、
`tests/test_stream_usage.cpp` 和 `.ci/review_stream_usage.py` 原字节保留。
新增 `.ci/test_stream_usage_history.py` 独立生成 711 个用例，并用 Fraction 验算费用。
`--verify` 回读原始输入/输出和 SHA256；`--negatives` 额外拒绝 22 种证据篡改。
包括布尔值冒充整数、重复 JSON 键、NaN、重新计算哈希后的错误用量/费用、漏项与正文泄漏。
校验器不会因为哈希一致就接受算术不一致的结果；这些检查不是报告来源认证。
原始流式报告的 15 种篡改拒绝门槛和远端 543 用例保持，不能与 711 用例互换计数。
`tests/stream_import` 注册基线 47 项及补充 47 项直接检查；CI 两平台均执行新增门槛。
每个基线/候选的具体执行记录独立保存，不将测试数量当作实际用户场景数量。

官方协议参考（2026-09-25 检索；兼容范围以本模块明确子集为准）：
- https://developers.openai.com/api/reference/resources/chat/subresources/completions/streaming-events
- https://developers.openai.com/api/reference/resources/responses/streaming-events
- https://platform.claude.com/docs/en/build-with-claude/streaming

### 整合与回退

本轮不把 0a7d0385 的旧完整补丁覆盖到仓库。以 817d222a 的修复为准，仅增加补充
测试、严格证据检查、示例与文档，并保持全部既有 CI 步骤。回退本次补充提交不会
删除既有产品修复。没有变更数据库、外发/写入许可、超时、发行资产或 Issue #40。
