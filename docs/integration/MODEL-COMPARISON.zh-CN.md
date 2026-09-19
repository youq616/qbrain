# N47S：从任务包执行模型 A/B

工具使用 Chat Completions JSON 接口，不是已登录 Claude/Codex 客户端测试。
`prepare` 和 `score` 不联网；只有明确授权的 `execute` 才调用指定端点。Python
是可选评测工具，不是应用服务。请使用含 N47S 的仓库源码；N47R 公开包未被修改。

## 1. 新样本与离线计划

在仓库根目录打开 PowerShell，将程序路径、供应商完整地址和模型ID替换为实际值。
以下完整块只生成合成任务与离线计划，不调用模型供应商。目录和输出文件必须新建。

```powershell
$ErrorActionPreference = 'Stop'
$exe = 'C:\Qbrain\qbrain.exe'
$endpoint = 'https://YOUR-PROVIDER.example/v1/chat/completions'
$model = 'YOUR-EXACT-MODEL-ID'
python .\tools\acceptance\run_memory_tasks.py --binary $exe --host claude --output .\eval-new
if ($LASTEXITCODE -ne 0) { throw 'Engine evaluation failed.' }
python .\tools\acceptance\check_memory_task_run.py --directory .\eval-new --binary $exe --report .\eval-new-readback.json
if ($LASTEXITCODE -ne 0) { throw 'Engine readback failed.' }
python .\tools\acceptance\model_ab.py prepare --directory .\eval-new --endpoint $endpoint --model $model --output .\model-plan.json --max-completion-tokens 512
if ($LASTEXITCODE -ne 0) { throw 'Plan validation failed.' }
Get-FileHash -LiteralPath .\model-plan.json -Algorithm SHA256
```

正式盲测必须重新生成资料，不能使用已经公开答案的CI样本。`--host claude`只是
生成引擎事件格式，不启动真实Claude客户端。标准答案文件、原始命令日志和另一
对照条件的回答不能交给模型；不要挂载整个评测目录给可访问文件的回答Agent。

计划固定50题×有/无上下文两种条件，共100个独立请求。两条件使用相同模型和
输出设置；每题不带其他请求历史，不定义模型工具。每对相邻执行，对的顺序及条件
先后随机，不保证50对中每种先后顺序恰好各半。供应商会收到显式选择的上下文；
请只用合成资料，不混入真实聊天或密钥。`store:false`不等于认证远端绝不保留数据。

### v2计划与会话标签

v2计划固定`context_projection=opaque-session-ids-v1`。原始任务包逐字节保留在计划
中；外发时隐藏场景型任务编号，并将上下文`session_id`元数据映射为不透明编号。
原话、fact/event/item/source等证据不变。映射后JSON会重新序列化，不能将其称为
原始Hook完整字节输入。文字里真正出现的字符串属于原话，不作为测试标签删除。
旧v1计划必须重新生成并批准，不要修改字段伪装成已经批准的v2计划。

## 2. 明确批准后才执行

先核对供应商计费，并在本机安全设置`QBRAIN_EVAL_KEY`。不要把密钥发到聊天、写入
命令参数或提交到Git。工具没有默认付费供应商或模型，也不会自动创建账号。
确认计划中的端点、模型、资料和调用上限后，在同一窗口执行以下完整块；它会实际
发送请求，可能产生费用。

```powershell
if (-not $env:QBRAIN_EVAL_KEY) { throw 'Set the provider key locally before explicit execution.' }
$planHash = (Get-FileHash -LiteralPath .\model-plan.json -Algorithm SHA256).Hash.ToLowerInvariant()
python .\tools\acceptance\model_ab.py execute --plan .\model-plan.json --approve-sha256 $planHash --approve-endpoint $endpoint --approve-requests 100 --key-env QBRAIN_EVAL_KEY --output .\model-run-new
$executionExit = $LASTEXITCODE
if ($executionExit -eq 2) { throw 'Execution refused or local I/O failed. Inspect receipts; do not blindly retry.' }
python .\tools\acceptance\model_ab.py score --run .\model-run-new --key .\eval-new\evaluator-key.DO-NOT-SEND-TO-MODEL.json --output .\comparison-new.json
if ($LASTEXITCODE -eq 2) { throw 'Scoring input or output validation failed.' }
```

执行进程只接收计划，不接收标准答案路径；答案在另一个离线评分进程读取。上述
命令的参数与程序接口已核对；本轮并未在真实供应商上运行这段付费调用说明。

## 3. 接口、安全与失败边界

端点必须是HTTPS并以`/chat/completions`结束，不允许URL内密钥、用户名、查询串或
片段，显式端口0会被拒绝。默认校验证书及主机名，不跟随重定向、不重试、不自动
换模型、不使用系统/环境的隐式代理。连接条件不满足时不要关闭TLS校验来绕过。
仅`--loopback-test`允许数字回环HTTP，且拒绝密钥、始终标为`LOOPBACK_TEST`。

协议限定非流式JSON对象回答。不承诺所有兼容供应商及模型都支持这些字段。
需要旧`max_tokens`字段的服务，必须在prepare时明确指定`--token-field max_tokens`；
不会失败后偷偷改参数重试。部分模型可能不支持`store:false`或JSON对象模式，应先
确认接口兼容性，不能用失败请求证明模型质量。

每次输出设置为128–4096 tokens，响应正文最多1 MiB，socket/body超时可设1–120秒。
512×100只是请求输出设置之和，不含输入或可能的失败计费，不是美元预算。系统DNS
及连接行为可能影响墙钟时间，不能据此承诺严格全流程时长。未知费用保持null。

不完整、重复或含混的HTTP消息边界、未收到声明长度的正文、被截断的答案、拒绝字段、
工具调用、错误JSON/任务ID或非法用量均停止后续调用。没有用量的有效回答可以
评分，但整组token总数保持空，不按字符估算。两条件报告的模型版本不一致时不
输出可比解决率差值；相同请求配置也不能认证供应商内部模型或采样状态完全相同。

每次联网前保存started.json，结束后保存receipt.json，最后保存run.json。硬崩溃或
磁盘错误可能只剩started记录，代表执行/计费状态不确定，不能盲目重跑。工具不会
续跑或覆盖旧目录。失败与缺答仍保留每个条件50题分母。

合法且不含当前密钥的响应保留原字节；当前密钥回显（包括JSON转义形式）先脱敏
再保存，并拒绝该回答。错误HTTP正文或无法安全解析的JSON不保存，仅保留状态及
已取得的摘要信息。不保证清除未知敏感信息、密钥碎片或其他变形，目录仍需保护。

## 4. 正确解释结果

execute返回0表示100次请求均返回合法完整答案，不表示回答正确；返回1表示
不完整；返回2表示输入/授权拒绝或本地I/O问题。score也按完整性而非正确率决定
退出码，详细依据性正确率和25题共同可答任务解决率见comparison-new.json。

供应商token数是供应商报告值，不是已认证账单。API对照不是客户端自动消费证明；
`host_consumption_verified`和`provider_provenance_verified`始终false。测试响应器
提供的答案与token数是夹具，绝不是实际模型结果。本阶段真实模型和登录客户端
仍未执行，必须在授权环境取得实际证据，不能用更多模拟测试替代。

本工具不是针对恶意操作者/任意二进制的沙箱，也不是任意自然语言、规模性能、
通用语义或提示注入防御评测。请保留源码版本、原始计划、请求响应与回执，避免
在准备、执行、评分之间混用版本。仅本地哈希一致不证明远端身份或账单真实性。

官方接口依据（2026-09-19核对；未固定供应商价格或型号清单）：
- https://developers.openai.com/api/reference/resources/chat
- https://docs.python.org/3/library/http.client.html
- https://docs.python.org/3/library/ssl.html#ssl.create_default_context
