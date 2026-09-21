# 隔离式 MCP 运行自检（N48D）

本模块检查一个已信任的 Qbrain 程序能否启动、完成限定的 MCP 握手、返回工具目录、
响应 ping 并正常退出。它不修改客户端配置、不调用记忆工具，也不传入现有脑库。
需要包含 N48D 的源码构建；当前 N47X 公开包没有 mcp-check 命令。

## 先查看，再明确批准

下面分别在 PowerShell 中执行，路径替换为已经核验的实际程序。预览不启动子进程，
不创建自检工作目录，不打开默认脑库。先检查显示的 binary、arguments、timeout_ms
及隔离政策，然后把实际 approval_sha256 填入第二条命令；不要使用示例占位符。

```powershell
& 'C:\Qbrain\qbrain.exe' mcp-check preview --binary 'C:\Qbrain\qbrain.exe' --timeout-ms 10000
```

```powershell
& 'C:\Qbrain\qbrain.exe' mcp-check run --binary 'C:\Qbrain\qbrain.exe' --timeout-ms 10000 --approve-sha256 '<预览返回的64位approval_sha256>'
```

运行前会重新核对程序字节、路径、许可属性、超时和固定政策。任何批准条件改变都
需要重新预览；指纹不是签名，也不能证明来源可信。命令说明按实现复核，未在用户
本机执行。本轮无需用户现在安装或转交本地 Agent。

## 自检实际做什么

新临时目录用作 HOME、数据目录、工作目录和子进程临时目录。环境采用固定白名单，
不转交供应商密钥、默认脑库变量或父进程的写许可；命令固定为：

```text
serve --brain probe --tool-profile memory
```

初始化、initialized 通知、tools/list、ping、关闭标准输入和等待退出组成整个流程。
协议固定为当前受测服务器支持的 MCP2024-11-05、按行 UTF-8 JSON；不宣称支持最新
或任意 MCP 版本。目录要求六个已知工具及回执/批量路由的基本声明，不实际调用它们。
因此较旧的真实 Qbrain 程序也可能因缺少路由而返回 catalog_required_routes_missing，
不能据此判断该旧程序无法用于所有其他用途。

成功 result=ISOLATED_MCP_VERIFIED 且退出码为0；运行不合格退出码为1，参数或批准
预检查失败退出码为2。initialize_verified、catalog_verified、ping_verified 与
clean_shutdown_verified 分别表示实际观察到的阶段，不可相互替代。

## 预算和结果隐私

默认协议等待10000毫秒，可设1000–30000。单帧最大65536字节，stdout累计262144，
stderr累计65536，最多16条已收到消息（包含允许的日志通知）；报告最多8192字节。
达到上限不必报错，超过才拒绝。等待共用一个协议期限，不给每个阶段重新分配预算。
同步启动、文件系统调用及内核终止过程不受严格总墙钟截止保证。

运行报告不包含任意子进程输出、环境值或本地路径，只给固定阶段/错误码、计数、
摘要与清理状态。preview 为了批准目标会显示路径，不能将它当作脱敏报告。
stdout/stderr 的计数不是原始内容；单个错误码不足以反推出历史故障的根因。

## 清理失败时保留，而不是强删

Windows 使用本次创建的 Job，观察直接进程结束及 Job 无活动进程；Linux 使用
本次私有进程组，并在清理前保留未回收的直接子进程身份。两者实现不等于可以证明
任何逃离管理范围的恶意后代都已退出。进程和目录清理共用2000毫秒等待预算。

仅明确的 Windows 共享/锁冲突允许有限等待，每次重新核对原目录身份。目录被替换、
其他错误、持续占用或进程清理无法确认时，返回 cleanup_incomplete 并保留临时目录。
workspace_cleanup_error 是可能存在的系统整数错误码，不是原始路径或错误文本。
不要对临时父目录作通配符强删，也不要根据过期报告删除其他目录。必要时在本机
核实对应自检进程和目录归属，再按明确范围处理。

## 不代表哪些验收完成

选定程序仍以当前用户的 OS 权限执行。新 HOME/环境只是逻辑隔离，不是安全沙箱、
禁网或对敌意可执行文件的防护。只运行已经信任的 Qbrain 程序。

本命令没有 tools/call、模型请求或真实脑库参数，不证明真实客户端已加载该配置、
模型采用记忆或写授权有效；报告中的 host_consumption_verified、
write_authorization_verified 和 os_security_sandbox 均为false。N48A/B/C的OpenCode
配置管理、真实宿主、模型质量费用、PG与签名验收仍独立存在。Issue40保持打开。

[完整工程审核](../nodes/N48D-HARD-AUDIT.md) · [精确证据](../nodes/n48d-evidence/SUMMARY.json)。
