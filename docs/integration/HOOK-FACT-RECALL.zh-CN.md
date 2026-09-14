# N47D：显式开启 Hook 事实召回

默认行为不变。安装时单独指定 `-EnableFactRecall`，允许本项目 Hook 在
SessionStart 和 UserPromptSubmit 中自动提供已经存在且证据有效的事实。
这不会自动创建事实；事实仍通过已授权的 fact/MCP 显式写入接口建立。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Install-QbrainMemory.ps1 -HostName Claude -ProjectPath "D:\Projects\MyProject" -Binary ".\qbrain.exe" -EnableFactRecall
```

`-EnableCapture` 与 `-EnableFactRecall` 是独立开关：前者允许本地会话采集，
后者允许事实进入客户端上下文。仅开事实召回不授权采集或 MCP 写入，也不会开启
Qbrain 模型提取服务。但 **Hook 输出会进入所选客户端的模型上下文，可能由该客户端
发送给它配置的模型服务**。没有额外 Qbrain 模型调用不等于没有资料外发。
不要绕过客户端项目、Hook 和工具信任提示。

`-Action Status` 的 `fact_recall_enabled` 表示该项目已安装配置的严格布尔开关。
重新安装时不提供该开关即关闭；卸载仍按原所有权规则移除本次接入并禁用保留配置，
保留脑库和备份。不会修改用户全局客户端配置。使用当前同一预览包的 EXE 和安装器，
旧二进制不支持新开关。Codex 可用 `-HostName Codex`，但具体客户端登录和事件触发
需要实机验证，进程夹具通过不能代替真实模型消费验收。

## 查询、组合与预算

SessionStart 读取最近的有效 active 事实；UserPromptSubmit 使用既有词项提取器取
最多8个不同的字面词项，在一条候选查询中匹配，查询总量最多1024 UTF-8字节。
这是字面检索，不是语义推断，也不是中文分词；没有可用词项的提示不会退化为枚举。

命中事实和全部有效的直接显式冲突方组成完整组，优先放入上下文。普通记忆只填充
剩余空间；若记忆是某个已有事实的证据，或者与该来源事实的完整原话完全相同，
则不再作为单条记忆输出，包括已撤回/替代事实。否则超预算冲突或已撤回事实可能
通过普通记忆重新出现。原始 memory_read 接口不改变；这种抑制只适用于新开启的
Hook组合模式。其他来源的同文事实不影响本来源普通记忆。

`recall_bytes`（512..8192，默认4096）约束**完整序列化 Hook JSON**，不只计算
additionalContext 字符数；输出行末换行另加1字节。`max_items`（1..16，默认8）
计算“事实组 + 普通记忆条目”总数，一个事实组可以包含多个完整冲突方。预算不足
不会截断原话或拆组，`truncated=true` 表示不完整；极小预算可能只输出空对象。

一个 SQLite 读事务贯穿两类内容。查询期间其他连接完成遗忘，本次仍可返回完整的
既有快照，下次调用重新校验证据；不能撤回已经进入客户端历史的字节。事实组每个
相关事件重新加载，不用旧会话去重屏蔽版本或反证变化。普通记忆保留既有去重规则。
每次事件事实部分共享512次证据校验/8MiB原文处理上限；候选、字节和工作限制不是
数据库扫描行数或硬实时保证。事实只展开直接关系，不自动判真假或选择赢家。

配置中的 `fact_recall` 必须是 JSON boolean；字符串 `"true"` 不视为授权。错误配置、
非法项目路径或组成失败保持 Hook 非阻塞，不能返回部分构建的冲突组。状态和 trace
不保存原话/查询词；`host_consumption_confirmed=false` 不代表失败或成功，仅表示
没有真实客户端消费证据。

## 免编译专项

包内脚本只运行独立临时数据、合成 Hook 事件，不调用真正登录的客户端：

```powershell
python -B .\verification\test_hook_fact_process.py --binary .\qbrain.exe --report "$env:TEMP\qbrain-hook-facts-check.json"
```

报告区分源码归因与行为结果：从 Release 中独立运行不能声称重新编译或重新认证
仓库源码。本阶段不增加数据库迁移、语义提取、自动冲突解决、画像、衰减或PG支持。
