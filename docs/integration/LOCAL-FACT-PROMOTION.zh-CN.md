# N47E：明确开启的本地事实整理

默认关闭。安装时同时明确同意采集和事实整理：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Install-QbrainMemory.ps1 -HostName Claude -ProjectPath "D:\Projects\Example" -Binary ".\qbrain.exe" -EnableCapture -EnableFactPromotion
```

`-EnableFactPromotion` 必须配合 `-EnableCapture`，否则在配置写入前拒绝。需要自动
提供事实上下文时再加独立的 `-EnableFactRecall`，不会因开启整理而自动开启召回。
三项开关相互区分；不改变现有客户端权限、Qbrain 模型外发许可或 MCP 默认写拒绝。
重装不传某开关即关闭它；Status 的 fact_promotion_enabled 报告有效状态；卸载
禁用本次接入，不删除已有事实或脑库。

## 自动做什么

只在 UserPromptSubmit 被实际采集，并且由既有本地规则完成提取后，将完整用户
原话整理到已有 N47A 事实表。已有规则识别“我偏好”“我决定”“I prefer”等
明确前缀；持久化方法为 explicit-markers-v1。不是通用语义理解或模型分类。
助手消息、没有规则命中的事件、被拒绝/过期/篡改/遗忘的证据不被提升。
脑库 memory.writeback=off 时采集不会发生，也不会绕过它整理事实。

predicate 是固定的 memory.preference、memory.decision、memory.commitment、
memory.lesson、memory.event、memory.fact；哪些类别能被提取仍受既有 salient/all
策略约束。object 保留原文全部字节及否定内容，confidence=null。不同原话不会自动
判断矛盾、选择赢家或替代旧事实。调用方仍需显式声明矛盾/替代。

同一来源、同一固定 predicate、完全相同原话会附加证据，而不重复创建事实。
重复处理相同 item 不写库、不增加 revision。存在多个符合条件的旧事实时优先
已有 item 附着，否则按 created_at/fact_id 选择最早者；不自动合并不同 predicate。

同源同句存在任何 retracted/superseded 事实时，自动整理会跳过，避免用另一个
事件绕过撤回；这也可能保守地跳过其他 predicate 的同句。它不改变手动 create
行为。每事实最多16份支持，超限明确记录 skipped_limit，不能另建事实绕过限额。

## 手动补处理一个已有本地提取事件

```powershell
.\qbrain.exe fact promote --brain example --source default --event <64位event_id>
```

也可用现有 MCP memory_write 的 action=fact_promote、event_id、source_id；仍需
明确的 --allow-write 及允许的 source。此动作不接受 payload、method 或 manual，
也不读 stdin。缺失、错误来源或非本地提取事件会被拒绝。它不会发起提取/模型调用。

结果只含 event/item/fact 标识、predicate、状态、revision、outcome 和计数，不重复
输出用户原话。total 等于 created、attached、duplicate、skipped_retired、
skipped_limit 之和。completed 可以含有明确的跳过项，不代表每句都新建成功。

一次最多32个已提取 item。全批次先校验证据，再在同一写事务中重新核对和写入。
中途失败不保留部分事实或部分证据修改。首次合法写入仍沿用N47A的“先备份并初始化
可选模块，再执行业务写入”；如果之后的批次失败，准备好的空表或备份可能留下，
不能把业务回滚说成全部磁盘操作回滚。所有后续事务等待保持有界，无自动反复重试。

## Hook 执行顺序和错误

先读取旧上下文，结束读取快照，再采集→本地提取→事实整理。所以当前输入不会被
伪装成更早的记忆；下一次相关事件/新会话才可能召回它。last-trace.json 中的
fact_promotion_status 为 not_run、completed 或 failed；成功时记录分类计数。
失败独立于先前 capture/extraction 成功，不抹掉已经采集的合成诊断证据、不自动重试。
排除故障后可用 event_id 显式重试。trace 不保存原话或完整数据库异常。

遗忘仍按支持事件处理：删除一份支持不会抹除另一个未遗忘事件；最后支持被删除
时由已有触发器删除事实副本。备份、WAL、已经给客户端的上下文不构成安全擦除。
关闭自动整理不等于撤回已存在事实，后者需明确 retract/forget。

## 验收边界

本阶段不新增数据库表、模型服务、MCP 工具名称或权限。已有客户端可能将获得的
上下文发送到其模型；没有 Qbrain 新模型调用不等于没有客户端外发。合成 Hook
事件、安装器测试不是已登录 Claude/Codex 的模型消费验收。

包内 verification/test_promotion_process.py 可用现有 Python 运行在独立临时脑库，
它依赖同目录 test_hook_fact_process.py（用于报告来源），必须完整解压同一包：

```powershell
python -B .\verification\test_promotion_process.py --binary .\qbrain.exe --report "$env:TEMP\qbrain-promotion-result.json"
```

此脚本只运行合成 CLI/MCP/Hook 事件，不启动真实客户端，也不需要编译器。
