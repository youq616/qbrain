# Qbrain N48K：可直接运行的 Windows 集成候选包

本包固定原生源码24345f85（已合并N48J），重新构建Windows x64程序，并携带安装器、
UTF-8桥、模型评测工具、费用示例和能力说明。不需要编译环境、Docker、WSL或Python
常驻服务。仅可选评测脚本需要Python。仍为未签名开发候选，非稳定版。

## 核验并解压到新目录

从本次交付取得 `qbrain-windows-x64-n48k-candidate.zip`、`SHA256SUMS.txt` 和
`ACCEPTANCE.json`。先在可信交付记录中核对ZIP摘要，再执行下列PowerShell代码。
ZIP内自带的MANIFEST不能替代外部可信摘要或代码签名。不要关闭杀毒、SmartScreen
或客户端安全检查，不要执行来源无法确认的EXE。

```powershell
$ErrorActionPreference = 'Stop'
$name = 'qbrain-windows-x64-n48k-candidate.zip'
$rows = @(Get-Content -LiteralPath '.\SHA256SUMS.txt' | Where-Object { $_ -match ('^[0-9a-f]{64}  ' + [regex]::Escape($name) + '$') })
if ($rows.Count -ne 1) { throw 'Expected one exact package checksum.' }
$expected = ($rows[0] -split '  ',2)[0]
if ((Get-FileHash -LiteralPath ('.\'+$name) -Algorithm SHA256).Hash.ToLowerInvariant() -cne $expected) { throw 'Package hash mismatch.' }
$target = Join-Path (Get-Location).Path 'qbrain-n48k'
if (Test-Path -LiteralPath $target) { throw 'Use a new extraction directory.' }
Expand-Archive -LiteralPath ('.\'+$name) -DestinationPath $target
$exe = Join-Path $target 'qbrain.exe'
$installer = Join-Path $target 'scripts\Install-QbrainMemory.ps1'
& $exe version
if ($LASTEXITCODE -ne 0) { throw 'Native version check failed.' }
```

应用内部版本号可能仍显示2.0.0，不代表稳定版验收；构建身份以固定源码和EXE摘要为准。
解压/运行程序本身不会替你安装Hook或批准采集。保留旧目录，不原地覆盖运行中的程序。

## 从N47X升级：记忆和用户配置保留

先关闭相关Agent进程，备份 `%LOCALAPPDATA%\Qbrain\` 及项目客户端配置。保持原有
项目和BrainId，使用新目录的安装器与EXE。安装器已有事务/恢复机制，本次不改其
语义，也不添加自动迁移、后台更新或全局设置修改。

下面命令中的项目路径和脑库标识必须换成真实值。Claude使用`-HostName Claude`，
Codex使用`-HostName Codex`。命令仅演示默认不采集的接入：

```powershell
& $installer -HostName Claude -ProjectPath 'D:\Projects\MyProject' -BrainId 'my-brain' -Binary $exe
& $installer -Action Status -HostName Claude -ProjectPath 'D:\Projects\MyProject'
```

明确同意后才分别增加 `-EnableCapture`、`-EnableFactPromotion`、`-EnableFactRecall`。
事实整理还要求采集许可。重装省略的开关会关闭，不默认继承过去许可。MCP写权限
仍独立控制。遇到恢复提示先查状态，不删除事务记录、不强行覆盖外部配置变化。

卸载集成不删除脑库和历史使用回执：

```powershell
& $installer -Action Uninstall -HostName Claude -ProjectPath 'D:\Projects\MyProject'
```

OpenCode使用原生`opencode preview/install/status/audit`等命令，其格式版本与权限
要求见包内 `docs/integration/OPENCODE-LIFECYCLE.zh-CN.md`。没有自动安装Agent，
也没有验证所有主流Agent已登录后的实际记忆消费。

## 包内已整合的功能

包括N47Y/Z回执完整性和批量预览/回滚、N48D隔离MCP自检、N48E OpenCode生命周期、
N48F/G/H精确费用与非流式/流式用量导入、N48I配对费用对照、N48J执行记录费用桥接。
对应说明和13个合成费率/费用示例位于`docs/integration`和`examples/cost`。
历史说明中“旧N47X不包含此命令”仍正确；本包已包含，无需按旧段落重新编译。
源码示例路径`build/cl/qbrain.exe`应改成当前包的`qbrain.exe`。

在包目录的 **cmd.exe** 可运行一个不访问脑库或供应商的例子：

```bat
qbrain.exe cost compare < examples\cost\compare-basic.json > comparison.json
echo %ERRORLEVEL%
```

这应返回合成差额 `-0.000050000000` USD，不是现实报价或费用节省证明。
`tools/acceptance/model_cost.py export|verify`可选脚本处理已有N47S执行目录。
只有原`model_ab.py execute`在明确批准计划、端点及请求数之后才联网并可能产生费用。
新费用桥接本身离线、不读密钥和评分答案；范围仅计划内主请求，不是全流程总费用。

## 如何理解验收记录

ZIP内容在构建后不改写。内部MANIFEST的`BUILT_NOT_YET_ACCEPTED`是构建时状态，
之后由外部`ACCEPTANCE.json`绑定同一ZIP与原始Windows测试结果；两者不矛盾。
包文件清单和摘要可复核重复打包、缺失文件和字节篡改，但不是来源认证或代码签名。

本轮必须实际验证：固定源码原生构建和原60组、解压程序的完整回归、包内评测工具、
PowerShell5/7安装/恢复及N47X升级。具体已执行/未执行范围以外部验收记录为准。
不据此宣称真实客户端记忆消费、真实模型效果、全流程成本、PG全面对等、签名或
稳定v1完成。Issue40启动超时根因仍未知；包通过不是该问题已修复的证据。
