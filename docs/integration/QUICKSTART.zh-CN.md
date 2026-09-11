# Windows 开发版：自动记忆接入

这是未签名开发版，不是完整 gbrain 等价实现。请将整个压缩包解压到固定目录，不要只移动 qbrain.exe；安装完成后不要移动程序或脚本。使用已有脑库前先自行保留备份。默认给不同 Agent／项目建立独立脑库，不改全局默认脑库。

在解压目录打开 PowerShell，修改项目路径后执行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Install-QbrainMemory.ps1 -HostName Claude -ProjectPath "D:\Projects\MyProject" -Binary ".\qbrain.exe" -EnableCapture
```

Codex 使用同一命令，将 `-HostName Claude` 改为 `-HostName Codex`。本批没有 Cursor 自动安装器。产品运行不要求 Python、Docker 或 WSL。

`-EnableCapture` 明确启用本地会话采集和保守规则提取。不带这个选项的安装或重装只启用召回，不自动采集，即使显式选择的共享脑库已经开启写回。安装不会授权调用外部模型，也不会给 MCP 开启写权限。

按照客户端自身的提示审核并信任项目与 Hooks；必要时重新启动客户端。Codex 可通过 `/hooks` 查看需要审核的定义。安装脚本不会跳过客户端的安全确认。

## 检查和卸载

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Install-QbrainMemory.ps1 -Action Status -HostName Claude -ProjectPath "D:\Projects\MyProject"
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Install-QbrainMemory.ps1 -Action Uninstall -HostName Claude -ProjectPath "D:\Projects\MyProject"
```

卸载删除本次安装拥有的配置，保留其他插件、记忆数据库和备份。已被另外修改的本工具配置不会强制覆盖。安装事务中断后，下次安装只能在确认文件符合事务记录时恢复；遇到歧义会停止。

## 记忆与分层读取

新会话先召回同项目的近期记忆；提交问题时按词查询相关记忆并采集当前用户原话。回答结束可以归档助手文本，但不会自动把助手猜测当成用户事实。默认不会读取宿主传入的聊天文件路径，也不会在每轮召回额外调用模型。

默认的 L0／L1 是明确标记的原文摘录，不是语义摘要；L2 是带版本校验的原文分页。可选的模型提取／摘要需要额外设置模型与外发许可，其效果没有在真实付费服务中验证。记忆可能漏提取、漏召回或过期，不能替代原文核对。

目录缓存、模型摘要和精简 MCP 的详细命令见 `WINDOWS-MEMORY.md`。预算单位是 UTF-8 字节，不是模型 token。随包 `verification/` 是合成资料测试，不能解读成真实用户任务的省费或回答质量保证。

`host_consumption_confirmed=false` 表示程序无法确认真实 Agent 模型已经消费了输出；它不等于安装失败。CI 通过表示真实 Qbrain 进程和安装脚本完成了已列出的检查，不等于每个客户端版本、Win11 环境、PostgreSQL 或在线模型都已验收。
