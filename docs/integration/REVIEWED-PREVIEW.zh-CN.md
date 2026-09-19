# Qbrain Windows 预览：N47M/N47N 修复版

版本标签：`windows-preview-c26ec5e5`。产品实际源码：
`c26ec5e512d9ba960b86c9ced5b9b4976b031f2c`。

本包将已经审核的 memory/context 参数与采集授权修复、search 字面参数边界
交付为可运行的 Windows x64 程序。原生 C++20，默认 SQLite；运行预编译程序
不需要编译器、Docker、WSL 或 Python 服务。仍是未签名开发预览，不是最终正式版。

## 1. 下载与版本核对

在本版本 Release 下载 `qbrain-windows-x64-reviewed.zip` 和本说明；另有
`PROVENANCE.json`、`SHA256SUMS.txt`、`SEARCH-ARGUMENTS.zh-CN.md` 及
`VALIDATION-EVIDENCE.zip`（原始验证日志与本次核验结果，不是程序包）。
不要误选 GitHub 自动生成的 Source code 压缩包，它不含预编译 EXE。

ZIP 为 2,117,939 字节，SHA-256：

`ec681a4599bf1b2a90f3848f5bf65b6d6a32e37254f32392d0709c43080b356c`

ZIP 是原始 c26 N44 测试工件的 inner ZIP，只有下载资产名称改变，未重编译或重打包。
EXE 为 4,077,568 字节，SHA-256：

`c35fadde8c8356b7243bf0b34cfd5c836bda27bb46da87eddcc79c1031bf05b5`

包内 MANIFEST.json 保留原始来源与各文件哈希。内置 README-FIRST 与旧版功能说明
保持测试时字节；本说明和旁附 SEARCH-ARGUMENTS 说明补充本次交付的新入口。
不要只凭 `version` 的继承版本号判定此次修复，使用上述源码和哈希。

## 2. 校验后解压到新目录，不覆盖旧版本

在 ZIP 所在目录打开 PowerShell，执行这一整段。目标目录已存在即停止：

```powershell
$ErrorActionPreference = 'Stop'
$zip = Join-Path (Get-Location).Path 'qbrain-windows-x64-reviewed.zip'
$target = Join-Path (Get-Location).Path 'qbrain-c26ec5e5'
if ((Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash.ToLowerInvariant() -ne 'ec681a4599bf1b2a90f3848f5bf65b6d6a32e37254f32392d0709c43080b356c') { throw 'ZIP checksum mismatch. Do not run it.' }
if (Test-Path -LiteralPath $target) { throw 'Target already exists. Use a new directory; do not overwrite.' }
Expand-Archive -LiteralPath $zip -DestinationPath $target
$exe = Join-Path $target 'qbrain.exe'
if ((Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant() -ne 'c35fadde8c8356b7243bf0b34cfd5c836bda27bb46da87eddcc79c1031bf05b5') { throw 'EXE checksum mismatch. Do not run it.' }
& $exe version
if ($LASTEXITCODE -ne 0) { throw 'Version check failed.' }
```

这段不会安装 Hook、开启采集、切换默认脑库或发起模型请求。不需要管理员权限。
哈希是完整性检查，不是代码签名；不要关闭防病毒软件或绕过客户端信任确认。

## 3. 选择项目接入：默认不采集

先关闭正在使用旧版的 Agent/后台进程，并备份 `%LOCALAPPDATA%\Qbrain\`。
将 `D:\Projects\MyProject` 替换为现有项目的实际绝对路径。在上述同一窗口执行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$target\scripts\Install-QbrainMemory.ps1" -HostName Claude -ProjectPath 'D:\Projects\MyProject' -Binary $exe
if ($LASTEXITCODE -ne 0) { throw 'Project installation failed.' }
```

Codex 使用相同命令，将 `-HostName Claude` 改为 `-HostName Codex`。这不是客户端
登录或完整宿主生命周期已验收的声明，仍需遵守该客户端的项目/Hook 信任设置。
不要用一个项目的安装成功代替另一个宿主的验收。

不传开关时不授予此安装的采集权限。明确需要自动采集才加 `-EnableCapture`；
明确需要本地事实整理才加 `-EnableFactPromotion`（同时必须加 `-EnableCapture`）；
明确需要事实召回才加 `-EnableFactRecall`。这些开关相互独立，不能从旧共享脑库
的设置推定本次同意。升级重装未重传开关会关闭相应功能，不会自动继承采集许可。
重新安装应使用旧安装对应的同一个 HostName 和 ProjectPath。

状态与卸载使用原安装器，不手工覆盖客户端配置：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$target\scripts\Install-QbrainMemory.ps1" -Action Status -HostName Claude -ProjectPath 'D:\Projects\MyProject'
powershell -NoProfile -ExecutionPolicy Bypass -File "$target\scripts\Install-QbrainMemory.ps1" -Action Uninstall -HostName Claude -ProjectPath 'D:\Projects\MyProject'
```

卸载保留脑库和备份。不要删除仍被其他项目引用的 EXE 目录。回退到旧版会重新暴露
对应旧解析问题；备份、先关闭使用进程，再用原安装器按相同项目/宿主接入是回退路径。

## 4. 新搜索语法

将 my-brain 替换为实际脑库。以下两种输入均不会把查询中的 --brain 当成选项：

```powershell
& $exe search --brain my-brain --no-vector --json --query '--brain sentinelneedle'
& $exe search --brain my-brain --no-vector --json -- '--brain sentinelneedle'
```

支持 --query VALUE、--query=VALUE、[options] -- literal words。未知、重复、缺值、
空查询及混合形式会在开库前拒绝。字面参数边界不是后端精确字串模式；纯标点未必
命中。--no-vector 只关闭查询向量，不关闭另行请求的 LLM 重排。详见旁附语法说明。

## 验证与未完成范围

产品验证基于固定 c26 的 N47N/N42/N44 及清单预检；N47N 两平台各361项解析检查、
226项进程检查/302次调用。包装和发布另重新核对固定原始工件，不重新宣称跑过
用户真实客户端。N47M/N47N 审核由协调者本人分离自审，不是第三方认证。

新 memory/context 的真实 PostgreSQL、所有宿主自动适配、通用语义合并/矛盾推断、
全量 ACL/DLP、完整模型质量/费用、模型实际消费和正式签名仍有未完成项。Hook 将
上下文交给授权客户端后，客户端可能发送给模型；没有 Qbrain 网络调用不代表
整个链路没有外发。forget 不等于备份/WAL 安全擦除。本预览不保证绝对无缺陷。
