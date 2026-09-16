# N47F：可撤销归档与只读生命周期检查

本阶段提供归档/恢复和来源限定的年龄检查，不实现语义合并、自动衰减删除或使用次数
统计。`stale`只是根据有效证据时间得到的提醒，不是新的事实status，也不表示原话
已经不真实。事实原有active、superseded、retracted状态机保留。

## 检查与操作

```powershell
.\qbrain.exe fact lifecycle --brain my-brain --source my-project --stale-after-days 180 --limit 10 --max-bytes 8192
'{"fact_id":"<64位事实ID>","expected_revision":1}' | .\qbrain.exe fact archive --brain my-brain --source my-project
'{"fact_id":"<64位事实ID>","expected_revision":2}' | .\qbrain.exe fact restore --brain my-brain --source my-project
```

示例JSON仅含ASCII。包含中文的其他写入继续使用同包Invoke-QbrainJson.ps1传输UTF-8。
从fact read或lifecycle结果读取实际revision，不复制示例中的1/2。每次真正改变归档
状态将revision加一；过时版本拒绝，当前版本的重复归档/恢复为幂等操作。两种操作
都只接受fact_id和expected_revision，必须经过原有来源及写授权。

MCP沿用六个原工具：`memory_read(view="lifecycle",stale_after_days=180,...)`，以及
`memory_write(action="fact_archive"或"fact_restore",payload="<JSON>")`。写权限仍默认
拒绝。lifecycle可按fact_id、predicate过滤；不接受query、event_id或include_history。
需要看退休历史仍使用原有facts视图的include_history，不用restore恢复退休状态。

## 归档不等于遗忘或隐私屏障

归档只使**该事实ID**不作为fact recall和显式开启的Hook事实召回入口。归档的事实
若是另一个未归档命中的有效直接冲突方，仍必须作为反证完整展示；不会为了减少输出
而制造“只剩一方”的错觉。fact read和fact conflicts是明确的检查操作，仍能读取它。

开启事实召回时，旧的普通记忆排除规则仍防止同句已绑定事实绕过归档进入Hook。
关闭事实召回后，普通记忆接口的既有行为不变，可能仍读到相同原话。归档不会从
客户端已有上下文、备份、WAL、页面搜索或其他独立同句事实中擦除内容。
相同ID的自动promotion追加证据不会清除它的归档标记；这不是同一句话的全局黑名单。
需要删除某事件对应记忆用forget，需要退休事实用retract/supersede，不混为归档。

恢复要求事实仍active且当前证据有效，不能复活已退休、过期、被篡改或已遗忘事实。
当最后证据删除使事实物理删除时，归档元数据通过外键级联一并清除，不留原话副本。

## 年龄与读取预算

年龄依据是当前有效支持项的最新created_at，**不是最后使用时间或用户确认时间**。
读取不写计数、不改变revision，也不生成置信度。stale_after_days范围1..36500，默认
180；到达阈值显示stale，未到阈值显示fresh。时间字段缺失/无效显示unknown，未来时间
显示clock_anomaly，年龄为null；不能把系统时钟异常当成更新证据。

只返回当前有有效证据的active事实。每次最多检查100个候选，限制1..50条结果、
512..32768个序列化JSON字节，复用事实层512次证据检查/8MiB原始证据工作预算。
放不下完整事实就停止并标记truncated；空且truncated不能解释为没有事实。数量和
字节上限并不保证SQL只扫描这些行或提供硬实时延迟。

一次读取从可选表检查至候选与证据加载使用同一SQLite快照；读过程中另一连接提交
归档，当前读可能返回完整旧快照，下一次调用看到新策略。不会提交调用方的事务。

## 数据与降级

普通读取和未归档事实的restore不建表。第一次有效archive会先备份磁盘脑库，再建立
独立memory_fact_lifecycle_module和memory_fact_archive，不改原有schema_version或
memory_fact_module。表准备和随后归档交易是两个步骤；状态操作失败可能保留备份和
空新表，但不会留下半个归档或错误revision。首次并发初始化可能生成多份有效备份。
元数据只包含事实ID、来源和归档时间，不复制用户原话。

**旧二进制不认识归档策略。** 降级运行旧版可能重新召回归档事实；不宣称降级仍保留
新策略。迁回备份需明确操作并考虑备份之后的新资料，不能自动覆盖用户库。
本功能没有更改安装器开关、默认采集、外部模型许可或全局客户端配置。原生测试和
Hook事件夹具不等于已登录客户端消费证明，未签名预览也不是最终发行版。
