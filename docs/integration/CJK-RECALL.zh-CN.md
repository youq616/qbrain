# 中文召回补修：N46F

本包是未签名 Windows 开发版。完整解压，不要用旧的固定464045e2哈希验收入口加载新包。
本次不迁移数据库、不重新生成向量、不改变模型外发或采集许可，也不实现N47事实图。

## 两个读取入口不能混为一谈

`memory_read` 读取经过提取的用户原话，query 是连续原文字串，不是语义问题。例如
原文“我偏好使用中文日志前缀”，查询“日志前缀”“日志”“中”应命中；查询“中文 前缀”
或“我的日志偏好是什么”不等于原文子串。空query读取近期记忆。它使用instr，不走FTS5。
本次仅澄清工具描述并增加回归，不扩大它的来源、时间、证据或删除规则。

普通 `search` 的SQLite全文索引则可能把连续中文作为一个词元。旧代码只有SQL失败时
才启用备用查询，正常返回零行并不会触发它。现在对有效、至多1024 UTF-8字节且包含
CJK字符的查询，保留全文匹配优先级，并用标题/正文/路径中的字面子串补满剩余候选。
百分号、下划线、引号不是这条补充路径的通配符或SQL。原英文全文路径保持不变。

补充结果不重复页面，保留来源与软删除过滤，全文结果优先，然后按更新时间、来源、
路径、页面ID稳定排序。正文预览会尽量包含匹配位置。最多返回500个候选不代表只扫描
500行：补充路径可能线性检查指定来源的页面。没有增加分词器、ANN或语义近义词推理，
也没有繁简转换；PostgreSQL未加同等逻辑。最终混合搜索仍受既有融合、截断和权限规则约束。

## 本机免编译专项复测

工具仅需现有Python，产品不新增Python运行依赖。在解压目录执行：

```powershell
$Manifest = Get-Content .\MANIFEST.json -Raw -Encoding UTF8 | ConvertFrom-Json
python -B .\verification\test_cjk_recall.py --binary .\qbrain.exe --report "$env:TEMP\qbrain-cjk-local.json" --source-commit $Manifest.source_commit --expected-binary-sha256 $Manifest.binary_sha256 --require-windows
```

先从仓库Release或交接提示词核对整个ZIP的固定SHA256，再信任包内清单。本脚本只用
新建合成脑库和隔离子进程做CLI/MCP测试，不改真实脑库，不调用模型、不安装Hook。
报告不得被当成真实Claude/Codex会话验收；Server2022不是Win11桌面。

原本地摘要把“memory_read中文漏召回”归因于FTS5，但没有随摘要提供原始issues.md。
仓库端用旧产品逻辑独立复现的是search漏子串；相同原文的memory_read已命中。
本地复测应检查旧日志实际工具名、query是否为连续原文、是否同source、是否已提取或过期。
保留最小合成复现，不上传真实会话或认证资料，不擅自改证据/权限过滤来得到成功结果。

仅在专项通过后，必要时用已登录Claude在新项目和专用脑库补测中文query。保留宿主
原有登录环境，只隔离Qbrain数据根；不得将答案、旧会话或报告注入新会话。安装与卸载
使用同包脚本，默认不碰正式项目。Codex自定义网关401需由账户所有者在本机安全处理；
不修改网关、打印密钥、猜测凭据，不反复调用直到碰巧成功，也不阻塞其他验证。

交接只需要一个提示词和一个脱敏报告包。未执行项目明确记为NOT_RUN/BLOCKED；
本机源码构建、全量C++回归和Windows专用探针仍可由仓库CI负责，不能继承为本机PASS。

## 设计参考

SQLite FTS5 unicode61和trigram说明：https://www.sqlite.org/fts5.html
没有直接换用trigram：它对不足三字符的MATCH有局限，并且会引入索引迁移与维护成本。
