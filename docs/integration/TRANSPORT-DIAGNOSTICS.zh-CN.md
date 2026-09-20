# 进程桥接诊断（N47W）

本功能在新源码的 `scripts/Invoke-QbrainJson.ps1` 中；旧 N47R 公开包不含它。
本阶段不更换安装包、不要求修改本机设置，也不自动运行付费模型或登录客户端。

## 变化与兼容

成功调用默认仍只返回 ExitCode、Stdout、Stderr。显式增加 `-IncludeDiagnostics` 才
附加 Transport 元数据；原始输入输出仍按原约定处理，不会改写成诊断正文。
子进程正常退出但返回非零码，不等于桥接失败；应分别检查 ExitCode 和业务结果。

通过参数与输入预检查后，桥接自身发生启动、传输或等待错误时，会抛出带
`Exception.Data['QbrainTransport']` 的异常。值为可单独提取的 JSON 字符串。
保留原 input/process/output timeout 消息；其他启动或传输异常改用固定消息，
不链入可能包含路径的原生异常。缺文件、参数绑定和输入预检查失败可能没有此字段。

默认超时仍为 10000 毫秒，允许范围仍为 100–120000。输入、进程等待和输出等待
共用启动计时后剩余的等待预算，不再为输入阶段重新分配完整预算。不会自动重试、
提高限制、关闭 UTF-8 检查或终止整个进程树。

## 一段可复制的只读版本查询示例

在源码根目录执行，替换为已核验的实际 EXE 路径。示例不采集会话、不写脑库。

```powershell
$ErrorActionPreference = 'Stop'
$exe = 'C:\Qbrain\qbrain.exe'
try {
    $r = & '.\scripts\Invoke-QbrainJson.ps1' -FilePath $exe -ArgumentList @('version') -InputJson '' -IncludeDiagnostics
    $r.Transport | ConvertTo-Json -Depth 4
    if ($r.ExitCode -ne 0) { Write-Error 'The child returned a nonzero exit status.' }
} catch {
    $e = $_.Exception
    $diagnostic = $null
    for ($i = 0; $i -lt 8 -and $null -ne $e; $i++) {
        if ($e.Data.Contains('QbrainTransport')) {
            $diagnostic = [string]$e.Data['QbrainTransport']
            break
        }
        $e = $e.InnerException
    }
    if ($null -ne $diagnostic) { $diagnostic }
    else { Write-Error 'No bridge diagnostic is available; check preflight conditions locally.' }
}
```

示例只展示提取方法，不代表已在用户机器执行。`Transport` 和 Data 中的 JSON 不含
路径、PID、命令参数、环境变量、密钥、输入、输出或异常正文。普通 PowerShell
错误记录仍可能含调用位置和脚本文本，成功结果的 Stdout/Stderr 也可能包含资料：
**只分享单独提取的诊断对象，不要因此认为整个 `$Error` 或执行结果都已脱敏。**

## 如何解释字段

| 字段 | 含义与限制 |
| --- | --- |
| code / phase | 固定错误类别，以及启动调用、输入、进程退出等待、输出排空或完成阶段 |
| timeout_ms / elapsed_ms | 配置等待预算，以及采样时的本次桥接累计耗时 |
| stage_ms | 已执行阶段的近似耗时；未进入的阶段为 null，包含该阶段的桥接辅助工作 |
| wait_budget_ms | 真正传入各阶段等待方法的剩余预算；未等待的阶段为 null |
| process_started | Process.Start 已返回成功，不证明应用、PowerShell 或模型初始化完成 |
| process_exited / exit_code | 清理前观测到的直接子进程状态，无法查询时为 null |
| input_closed / *_state | 输入是否已关闭，以及异步输入、标准输出和错误流任务状态 |
| observation | 固定为 before_cleanup；后续清理不会回写这份历史观察 |
| host_consumption_verified | 恒为 false，不能据此证明客户端采用了记忆 |

`process_timeout` 指进程退出等待超时；`output_timeout` 则可能发生在直接子进程已经
退出、但后代仍持有输出管道时。状态有采样时差，不是同时冻结的操作系统快照。
`transport_error` 可以用于流任务异常；例如严格 UTF-8 解码失败，不读取错误正文。

没有任何字段能单独证明 Issue #40 的旧超时根因。启动调用返回成功后，子进程内部
仍可能在初始化；需要结合有授权环境中的其他独立观测，而不能仅凭阶段名称断言。

## 时间、清理和保存边界

计时是桥接层观察，含本地辅助开销，阶段耗时之和未必等于最后 elapsed_ms。同步
操作系统启动不能由本脚本强制取消；输入关闭、异常整理和资源回收也不受严格的
总墙钟截止保证。等待预算耗尽后，已完成的任务仍可被即时读取。不要将本功能称为
任何运行环境都绝不超过 10 秒的保证。

原清理策略保留：必要时终止直接子进程，并有限等待其退出（2000 毫秒）；没有
新增任意 PID 扫描或整个进程树终止。输出捕获仍保持原有内存行为，本功能不是
输出大小限制器，也不是执行不可信二进制的安全沙箱。

不会自动把诊断写盘或上传，也不会修改安装好的 Hook 处理错误的方式。因此旧
客户端若自行吞掉异常，不能据此声称诊断已自动持久化。调用方可按自己的资料
保留规则保存提取后的 JSON；原检查失败或进程异常不应被批量自动重试掩盖。

Issue #40 继续打开：该历史超时的根因尚未确定，本阶段增加诊断能力并修复输入
预算口径，不把可控测试子进程的超时当作历史故障已被复现或修复。

参考：Microsoft .NET 文档 Process.WaitForExit(Int32)、Process.StandardOutput、
Exception.Data。两版 PowerShell 的实际原生测试与固定证据见本阶段审核记录。
