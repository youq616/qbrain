# Qbrain 当前交付状态

## 已合并并发布：N47J 分事件诊断与遗忘重放修复

[PR #26](https://github.com/youq616/qbrain/pull/26) 已合并，产品合并提交
`f45af31e06243b41184b9274c0fc39073e10dd0a`。实际产品／原生测试源码为
`2ec0c3daaa6d324bcc9f16a1ebacc88c63abe561`，源树
`37cfb0d5bd1df6501f0a42fe19d253e0e9e8b431`。
审核头 f75dab6b 相对产品仅增加/更新 docs 下6个文件，包括只读验证工具；没有改动
生产代码、原测试、产品工作流或包字节。合并提交与审核头无文件差异。

[预览 Release：trace-preview-2ec0c3da](https://github.com/youq616/qbrain/releases/tag/trace-preview-2ec0c3da)
已公开。产品 `qbrain-windows-x64-hook-trace.zip`，2,071,649 字节，SHA256：
`778ddfde895a3f6a48b8b7d007d8a94f2b93a41639054b8c920687438444d0df`。
完整解压，阅读 `HOOK-DIAGNOSTIC-CHECKPOINTS.zh-CN.md`。仍为未签名开发预览，
是原CI包字节，不是重新压缩或编译后的副本，不是整个项目完成。

## 实际能力和边界

保留 last-trace.json 兼容路径，另按两个固定host、五种固定事件分别保存最近一次
已接受处理的诊断。最多十个分事件槽，每条<=4096字节；后续SessionEnd不再覆盖
UserPromptSubmit的独立槽。同种事件的新调用仍覆盖旧记录，不是无限历史日志。

仅保存有限状态、阶段、计数、时间和session_key，不保存原话、回答、上下文、异常
文字、原始会话ID或凭据。独立尽力更新两个文件，诊断失败不阻断正常Hook输出。
被遗忘事件重放后明确记录capture_status=forgotten，不保留旧成功状态。local模式
记录failed/extract；deferred模式可以processed/complete，但不代表提取成功或记忆复活。

这是尽力诊断，不是持久审计或两个文件的原子更新。禁用、锁忙或前置拒绝可能没有
新记录，I/O失败可能留下旧记录；应检查事件、session_key和时间。processed不表示
模型消费，host_consumption_confirmed仍为false。关联哈希不是签名或匿名性保证。

## 已核实验证和本轮独立工程检查

产品运行35163779907及N42运行35163779904必需任务完成成功：完整Windows58注册组，
诊断单元9场景169断言在Server2025、Server2022、portable和Linux ASan/UBSan通过；
诊断进程66检查80命令在完整Windows、portable和sanitizer通过。80个Hook命令均按
非阻断契约退出0，但测试同时核对失败状态、上下文及遗忘内容没有重建。

当前收尾轮从848文件原始源码重新GCC14.2编译并执行单元9/169、进程66/80和175项
报告/注册校验，通过292项原始工件/源树/全66包成员/原报告/源码与脚本/EXE回读。
这些新增本轮执行是Linux检查；Windows结果来自单独核对的原生CI。此前补充探针
的历史结果按接收记录单独保存，不重复计数。可选校验器测试文件的上传被平台拦截，
未换通道绕过，未进入产品；该文件不影响原有产品测试和原包交付。

本阶段未发现未解决P0/P1，不保证不存在所有潜在缺陷。审核由协调代理在实现后
单独执行，不冒称第三方或子代理。诊断探针二进制未单独下载，身份依赖固定原始
报告和原打包时的实际文件校验。真实PG DSN仍明确SKIP-PG。

发布35175614044成功：绑定固定产品/审核头/已合并PR及原生任务，下载固定6工件，
执行292项离线检查后创建新草稿，下载并逐字节比对全部三个Release资产再公开。
未重编译、重打包、覆盖旧Release或开启通用未审核自动发布。

[阶段审核](docs/nodes/N47J-HARD-AUDIT.md) · [测试摘要](docs/nodes/n47j-evidence/SUMMARY.json) ·
[发布记录](docs/nodes/n47j-evidence/RELEASE.json)

## 既有能力与未完成范围

严格JSON输入、候选分页、显式原子批量、可撤销归档/恢复、只读支持年龄、本地规则
事实整理、明确开启的Hook事实召回、证据生命周期、显式冲突和含反证召回均保留。
安装默认开关、来源权限、遗忘、上下文预算和原数据模型未因N47J改变。

没有新Claude/Codex真实客户端会话验收；不重复N47E任务，不修改既有Codex认证。
通用语义合并、自动衰减、使用/确认计数、画像、PG对等、完整ACL/DLP、模型质量费用
和正式签名仍未完成。当前无需本地Agent接手合并或发布，也不需Token、额外权限、
编译器或再导出源码。必要本地任务仍只给一个完整提示词，文件先放仓库并固定来源。
