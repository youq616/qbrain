# N47J：按事件保留最近的 Hook 诊断

N47E实机验收中，最后的SessionEnd覆盖了last-trace.json，导致UserPromptSubmit的
直接处理记录未保留。N47J不增加原话日志，而在同一个安装器自有配置目录中，
保留每个host/event的最近一次已接受处理记录。`last-trace.json`兼容路径仍更新。

例如Claude输入处理记录为`trace-claude-UserPromptSubmit.json`；会话结束另写
`trace-claude-SessionEnd.json`，不会覆盖前者。支持claude/codex两种host及
SessionStart、UserPromptSubmit、Stop、PreCompact、SessionEnd五种事件，共十个
固定槽。相同事件的下一次调用会替换旧记录，不是无限历史或每个会话一个文件。

## 字段和定位方法

`format_version=2`。`host`与`event`均来自已校验值；`session_key`与既有去重状态
采用相同计算：SHA256(host + "\n" + brain_id + "\n" + source_id + "\n" + session_id)，
UTF-8、无结尾换行。它只用于关联本地已知会话，不包含原始身份文本或原话哈希；
它是化名标识，不是匿名化、签名或认证。

`completed_at_unix_ms`为生成该诊断时观察到的UTC Unix毫秒，可帮助区分旧记录，
不保证时钟永不回拨或严格排序。`status=processed`表示Hook的处理与去重状态保存
完成；`status=failed`配合`phase`定位在open、recall、capture、extract、promote、
state中的哪个阶段异常。promotion本身是独立的`fact_promotion_status`：即使Hook
整体processed，promotion也可能failed。检查它及六个结构化计数字段，不扫描文本
子串推断状态。失败记录不会包含异常原文、路径、SQL、prompt或原话。

`recall_count`、`fact_group_count`、`context_truncated`和`output_bytes`沿用实际
程序内观察值。输出字节不含stdout结尾换行，不代表客户端已接受。事实整理计数
仅在完成时记录；`provider_calls=0`沿用此Hook路径未配置独立模型调用的声明，
不是额外网络抓包计数。`host_consumption_confirmed`始终false，不能手动改为true。
这些文件能定位程序阶段，不能单独证明真实客户端或模型确实消费了上下文。

## 容量、失败和隐私边界

每个文件最多4096 UTF-8字节，只有允许的枚举、整数、布尔和化名标识。记录不保存
用户提问、原话、模型回答、additionalContext、内容指纹、原始session/source/brain
标识、异常文本或凭据。没有新schema、模型调用、MCP名称或安装启用开关。

写入在原runtime.lock内部，以同目录临时文件替换目标。事件槽和last-trace分别尽力
写入，不是两个文件的联合事务；任一失败不会阻止另一个或阻断正常Hook响应。
临时文件也采用同一固定名称，不会无限新增。未完成写入时可能残留旧记录或.tmp；
不能将“文件存在”误认作刚刚成功。已知读取者应核对event、session_key、时间和
实际上下文证据，而不是把任何一份旧记录当成本次验收结果。

禁用、无效JSON、非法项目、未知事件或锁忙等在取得诊断作用域之前就拒绝的调用
不会留新的记录。进程被强制终止、磁盘不可写或分配失败也不保证能记录；因此这
不是可靠审计日志、崩溃恢复协议或全事件计数器。仍受既有本地配置目录权限和
重解析路径信任模型约束，不声称防御拥有目录修改权限的恶意本地进程。

卸载仍仅移除本次拥有的接入并禁用配置，遵循原有自有目录保留语义；这些化名
时间记录不自动上传。无需读取真实脑库或扩大采集授权来使用此诊断。

## 免编译回归

在源码目录，用现有Python执行`.ci/test_hook_trace_process.py --binary <本版程序>
--report <新报告路径>`；它自行建立和清除合成脑库，模拟两种host事件，包含写盘
失败、损坏数据库和非阻塞验证。不使用已登录客户端或付费模型，不能算新的实机
验收。不需要重复N47E已完成的三个真实会话。
