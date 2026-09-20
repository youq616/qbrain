# Qbrain N47X：当前源码集成预览

本包从固定源码 b810d6898dcbbcd49bdbbed1d8473a3ac1c063e4 重新编译原生 Windows EXE，
整合 N47S 模型对照工具、N47T/U 使用回执与审计、N47V 路径保护、N47W 桥接诊断。
不是沿用旧 c26 EXE 后修改说明。应用无需 Docker、WSL 或 Python 服务；可选评测
工具需要 Python 3.10+。这仍是未签名开发预览，不是已完成真实效果验收的稳定版。

## 验证后再使用

只有同版本发布页、SHA256SUMS.txt、PROVENANCE.json 与验收证据相互对应时才安装。
校验和只能验证字节，不是代码签名；同时核对可信发布页给出的 ZIP SHA256。
不要使用 GitHub 自动生成的 Source code 归档代替程序包。

在下载目录执行以下 PowerShell 段，先验证并解压到**新目录**。它不安装 Hook 或采集资料：

```powershell
$ErrorActionPreference = 'Stop'
$name = 'qbrain-windows-x64-n47x-preview.zip'
$matches = @(Get-Content -LiteralPath '.\SHA256SUMS.txt' | Where-Object { $_ -match ('^[0-9a-f]{64}  ' + [regex]::Escape($name) + '$') })
if ($matches.Count -ne 1) { throw 'Expected one exact product checksum.' }
$expected = ($matches[0] -split '  ', 2)[0]
if ((Get-FileHash -LiteralPath ('.\' + $name) -Algorithm SHA256).Hash.ToLowerInvariant() -cne $expected) { throw 'ZIP hash mismatch.' }
$target = Join-Path (Get-Location).Path 'qbrain-n47x'
if (Test-Path -LiteralPath $target) { throw 'Use a new extraction directory.' }
Expand-Archive -LiteralPath ('.\' + $name) -DestinationPath $target
$exe = Join-Path $target 'qbrain.exe'
$installer = Join-Path $target 'scripts\Install-QbrainMemory.ps1'
& $exe version
if ($LASTEXITCODE -ne 0) { throw 'Native version check failed.' }
```

首次运行的安全提示、杀毒和客户端信任检查不应关闭。既有 CLI 内部版本字符串
可能仍显示 2.0.0，这是继承版本号，不等于稳定版验收；以本包来源/EXE哈希识别构建。

## 从旧 N47R 升级

先关闭相关 Agent/后台进程，备份 `%LOCALAPPDATA%\Qbrain\`。不要覆盖旧解压目录。
用新目录的安装器和 EXE 对同一实际项目、宿主重新安装；保留原脑库 ID。示例路径
必须替换，不要用占位项目或随意换脑库：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File $installer -HostName Claude -ProjectPath 'D:\Projects\MyProject' -BrainId 'my-brain' -Binary $exe
if ($LASTEXITCODE -ne 0) { throw 'Installation failed; inspect status before retrying.' }
```

Codex 使用 `-HostName Codex`。默认不开启采集/事实整理/召回。确有授权时分别添加
`-EnableCapture`、`-EnableFactPromotion`、`-EnableFactRecall`；整理同时要求采集。
重装时未传的开关会关闭，不会推定此前同意仍适用。旧脑库和事实不会为升级被清空。
如果有 pending 恢复记录或路径拒绝，先查状态，勿删除文件、关闭路径保护或强行重试。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File $installer -Action Status -HostName Claude -ProjectPath 'D:\Projects\MyProject'
powershell -NoProfile -ExecutionPolicy Bypass -File $installer -Action Uninstall -HostName Claude -ProjectPath 'D:\Projects\MyProject'
```

卸载保留脑库及历史使用回执，不代表安全擦除备份/WAL。大小写敏感或不可验证目录
仍明确拒绝，不能用此版本自动迁移两个仅大小写不同的项目。

## 包内新增能力

事实回执命令为 `fact report-use`、`fact revoke-use`、`fact usage`、`fact usage-list`。
回执只是授权调用方声称使用，不证明模型确实消费记忆或事实为真；读取不自动记账。
回执查询支持版本/撤回筛选与变化检测分页。原话、权限、版本绑定与撤回规则不变。

桥接脚本支持 `-IncludeDiagnostics`，失败可提取 Exception.Data 的 QbrainTransport。
只分享单独诊断对象，不要把整个错误记录或原始输入输出当作已经脱敏。

包内 `tools/acceptance/model_ab.py` 提供离线准备、明确授权的 API 执行和离线评分。
准备/评分不联网；执行须显式批准端点、计划哈希和100请求，密钥只留在本机环境。
没有默认付费模型或自动调用。运行脚本并不等于真实客户端登录验收。

具体命令见 `docs/integration/` 中各能力说明。其原文保留对应源码阶段的历史边界，
其中“旧 N47R 包不含功能”仍正确；本 N47X 集成包已经包含这些已验收源码，不再需要
为了使用上述功能单独编译。某些源码根目录示例的 EXE 路径应改为本包 `$exe`。

## 证据和剩余门槛

MANIFEST.json 枚举当前包的每一文件，BUILD-PROVENANCE.json 绑定固定源码、新EXE
和原生构建日志。内部状态保留构建时 BUILT_NOT_YET_ACCEPTED；通过后不改写ZIP，
后续外部 PROVENANCE.json/验收证据绑定同一ZIP哈希。

未宣布：真实已登录客户端采用记忆、真实模型质量/费用、PG记忆模块对等、正式签名
或全项目完成。Issue40 的历史 Codex 超时根因仍未知，诊断能力和整包通过都不是
该问题已修复的证明。旧发布资产保留，不自动删除或覆盖。
