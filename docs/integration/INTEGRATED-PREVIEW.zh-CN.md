# Qbrain N47R 集成 Windows 开发预览

这个集成包将原生程序、N47P 安装恢复修复和 N47Q 任务评测工具放在同一目录。
运行应用不需要编译器、Docker、WSL 或 Python 服务。评测工具另需 Python 3.10+。
这是未签名开发预览，不是正式稳定版，也不代表真实客户端或模型效果全部验收。

## 先区分候选与已经核验的发布

构建器只生成候选，不负责安装、原生测试或发布。包内 MANIFEST.json 的
native_bundle_tests=NOT_RUN、published=false 是**构建时状态**，不会在测试之后
修改 ZIP 来伪造新证据。后续验收与发布使用外部回执，必须绑定此 ZIP 的精确哈希。

没有同一版本正式发布页、SHA256SUMS.txt、PROVENANCE.json 和验收证据时，只作
工程候选保存，不安装。发布后也应检查这些文件对应同一版本，而非仅相信文件名。
不要选择 GitHub 自动生成的 Source code 压缩包代替程序包。

## 组件和完整性

原生 qbrain.exe 与字节传输桥保留 N47O/c26 原字节，EXE 没有重编译。
安装器采用 N47P/9feed 经原生测试的 CRLF 字节；六个评测工具来自 N47Q/11c7。
这个 ZIP **经过重新组装**，不能沿用旧 N47O ZIP 的哈希。新清单列出所有现有文件，
并分别标明三个组件的来源。provenance/N47O-MANIFEST.json 和旧 README 是历史
原件，不是新安装器或整个新包的验收证明。哈希不是代码签名。

原生 EXE SHA-256：
`c35fadde8c8356b7243bf0b34cfd5c836bda27bb46da87eddcc79c1031bf05b5`

新安装器 SHA-256：
`d802c230d2e5b0938b81baa115d5cf5b475aa855fce0df28f0305f00575fcc51`

## 验证发布后，解压到新目录

先关闭正在使用旧版本的 Agent/后台进程，备份 `%LOCALAPPDATA%\Qbrain\`。
在同一版本文件下载目录运行以下完整 PowerShell 块。它从唯一的校验和条目识别
ZIP；拒绝模糊条目、错误哈希、路径穿越和已存在的解压目录。还须核对可信发布页
公布的 ZIP 哈希，不要把同一不可信来源的自报哈希当作签名。

```powershell
$ErrorActionPreference = 'Stop'
$rows = @(Get-Content -LiteralPath '.\SHA256SUMS.txt' | Where-Object { $_ -match '^[0-9a-f]{64}  qbrain-windows-x64-n47r-(candidate|preview)\.zip$' })
if ($rows.Count -ne 1) { throw 'Expected one N47R product checksum entry.' }
$parts = $rows[0] -split '  ', 2
$zip = Join-Path (Get-Location).Path $parts[1]
if ((Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash.ToLowerInvariant() -ne $parts[0]) { throw 'ZIP checksum mismatch.' }
$target = Join-Path (Get-Location).Path 'qbrain-n47r'
if (Test-Path -LiteralPath $target) { throw 'Use a new directory; do not overwrite an existing installation.' }
Expand-Archive -LiteralPath $zip -DestinationPath $target
$exe = Join-Path $target 'qbrain.exe'
$installer = Join-Path $target 'scripts\Install-QbrainMemory.ps1'
if ((Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant() -ne 'c35fadde8c8356b7243bf0b34cfd5c836bda27bb46da87eddcc79c1031bf05b5') { throw 'EXE checksum mismatch.' }
if ((Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash.ToLowerInvariant() -ne 'd802c230d2e5b0938b81baa115d5cf5b475aa855fce0df28f0305f00575fcc51') { throw 'Installer checksum mismatch.' }
& $exe version
if ($LASTEXITCODE -ne 0) { throw 'Native version check failed.' }
```

这段只校验、解压与查询版本，不开启采集、不安装 Hook、不调用模型。
没有管理员权限要求；不要关闭防病毒或绕过客户端信任确认。

## 项目接入、升级与退出

把下面项目路径替换为实际已有项目的绝对路径，保留原来的 HostName 和 ProjectPath。
在上述同一窗口执行；使用 Codex 时仅把 HostName 改为 Codex：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File $installer -HostName Claude -ProjectPath 'D:\Projects\MyProject' -Binary $exe
if ($LASTEXITCODE -ne 0) { throw 'Project installation failed.' }
```

默认不采集。明确需要采集才加 `-EnableCapture`；需要本地事实整理才另外加
`-EnableFactPromotion`（同时必须启用采集）；事实召回另加 `-EnableFactRecall`。
升级重装未重传的开关会关闭，不会从共享脑库推定本次同意。安装成功也不是
客户端已实际消费记忆的证明。卸载保留脑库与备份；不要删除仍被其他项目引用的目录。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File $installer -Action Status -HostName Claude -ProjectPath 'D:\Projects\MyProject'
powershell -NoProfile -ExecutionPolicy Bypass -File $installer -Action Uninstall -HostName Claude -ProjectPath 'D:\Projects\MyProject'
```

中断后先查 Status；`recovery_required=true` 时不要直接删除 pending.json。
关闭其他配置写入者，再用相同项目/宿主和明确开关重试原操作。详见包内
INSTALLER-RECOVERY.zh-CN.md：这是可重试的多文件文本事务，不是全局原子事务；
最后比较之后的竞争、原 BOM/编码保留和脑库初始化回滚并未保证。

## 包内评测工具

评测命令需要新输出目录，仅读写临时合成数据，不读取真实脑库：

```powershell
python "$target\tools\acceptance\run_memory_tasks.py" --binary $exe --host claude --output '.\evaluation-n47r'
python "$target\tools\acceptance\check_memory_task_run.py" --directory '.\evaluation-n47r' --binary $exe --report '.\evaluation-n47r-readback.json'
```

--host 是事件格式，不启动已登录的客户端。50项任务与两个评分指标的使用说明见
固定 N47Q 源码的 docs/integration/TASK-EVALUATION.zh-CN.md。不要把答案文件、
原始命令目录或另一条件下的答案提供给回答模型；正式盲测须生成新数据并隔离会话。
ENGINE_PASS 不等于模型回答通过。真实模型/宿主/费用未执行时仍为 NOT_RUN/null。

真实客户端自动消费、模型答案/费用、规模语料、PG 对等、完整 ACL/DLP、通用语义
合并与衰减、正式签名等仍需单独验收。本包不会自动启动付费模型或改变采集许可。
