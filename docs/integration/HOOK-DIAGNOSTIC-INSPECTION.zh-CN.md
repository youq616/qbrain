# N47K：只读查看各事件 Hook 诊断

```powershell
.\qbrain.exe hook diagnostics --config "C:\absolute\installed\config.json"
.\qbrain.exe hook diagnostics --config "C:\absolute\installed\config.json" --event UserPromptSubmit
.\qbrain.exe hook diagnostics --config "C:\absolute\installed\config.json" --session-key "<已有诊断中的64位小写十六进制session_key>"
```

config 必须是本机已安装的 Hook 配置的绝对路径；示例路径/占位符需换成真实值。
这不是安装命令，不初始化脑库、不触发 Hook，也不读取提问 stdin。普通
`hook --config ...` 的行为不变。不提供 MCP 入口，避免给模型增加任意本地文件读取。

只查看该配置 host 的 SessionStart、UserPromptSubmit、Stop、PreCompact、SessionEnd
五个固定文件，可用 --event 缩小为一个；不扫描其他文件，不回退 last-trace，不读取
.tmp。不要求脑库存在；诊断配置 disabled 时也可查看历史记录，但不代表 Hook 仍开启。

## 如何解释结果

顶层 result=INSPECTED 表示“查看操作已完成”，不是产品验收 PASS。每个 slots 项包含
事件和 state：present 为格式严格有效且匹配筛选条件；missing 为未观察到文件；
invalid 为无效/不支持/字段冲突或未知字段；oversized 为超过4096字节；unsafe_path 为
链接、重解析点、目录或非普通文件；unreadable 为无法读取；session_mismatch 为格式
有效但不属于所选关联标识。非 present 项不返回原始内容或错误文本。

present 项返回完整、重新验证的 N47J 元数据。坏文件中的额外字段，即使只是多一个
备注，也会导致 invalid，不会悄悄舍弃后当成有效记录。重复解码JSON键、错误数值类型、
不一致的状态/阶段、错误host/event与host_consumption_confirmed=true均拒绝。
配置 version=1、host=claude|codex、enabled必须为布尔；不追踪配置中的脑库或其他路径。

`status=processed` 只说明 Hook 已处理。`capture_status=forgotten` 是遗忘事件重放，
不能称为重新采集成功；local模式可以failed/extract，deferred可以processed/complete。
诊断没有证明模型消费，因此顶层host_consumption_confirmed和record_authenticity_verified
始终false。本地可写者能伪造合法元数据；session_key既非身份认证，也非匿名性承诺。

## 安全、限制与副作用

只读OS句柄，禁止新增锁文件、日志、目录或脑库。单配置最多64KiB，最多读5个4096字节
记录，完整JSON报告<=32768字节（stdout另有一个换行）。不会复制原话、异常文字或真实
文件路径。命令参数/配置错误返回固定JSON错误和退出码2；成功输出INSPECTED返回0，
即使部分/全部记录无效。不能仅用退出码0判断自动记忆流程通过。

各文件是独立读取，非跨事件原子快照；缺文件不等于未执行、无效或会话不匹配不等于
发生产品缺陷。结合事件、记录时间和会话关联判断；没有自动时效评分或成功推断。
目录/最终文件拒绝静态链接与Windows重解析点；Windows仅接受盘符绝对路径，不接受
UNC/设备路径或备用流。此限制是保守本地排查策略，不改变原Hook安装/写入功能。
不保证能抵御持有目录写权限者持续改写父目录的竞争，不阻止有权创建硬链接者；
不保证磁盘I/O硬实时、可靠审计持久性或跨文件一致性。任何诊断都不能代替原始证据。

本命令不需要模型账号、GitHub凭据、额外采集许可或安装编译器；使用同包EXE即可。
已有N47E真实客户端验收无需因此重跑。没有新数据库迁移或运行服务，源码回滚只撤销
查看入口，不影响已存N47J记录。
