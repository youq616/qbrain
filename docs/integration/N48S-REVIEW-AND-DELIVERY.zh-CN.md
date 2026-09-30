# N48S：本轮统一交付与源码补充

本轮交付一份完整下载包，不需要拼接 N48O/P/Q/R 等单模块 EXE。
包含原始 `qbrain-windows-x64-n48s-candidate.zip`、原 CI 外部 ACCEPTANCE、独立复核报告和
固定摘要。原运行 ZIP 未被重写，包内 BUILT_NOT_YET_ACCEPTED 是构建时的记录，不是后来
的失败状态；实际限定验收结论在外部 ACCEPTANCE.json。

## Windows 使用

将外层交付包解压到新目录，在该目录打开 PowerShell。以下操作只校验并解压，不安装、
不修改脑库、不启用采集，不发送模型请求：

```powershell
$ErrorActionPreference = 'Stop'
$zip = Join-Path (Get-Location) 'qbrain-windows-x64-n48s-candidate.zip'
$expected = 'a326ed8e031903935e860a37b8a44f5eaa170a0c7becc697afe23c9b609c332c'
if ((Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash.ToLowerInvariant() -cne $expected) {
    throw '运行包摘要不符，停止。'
}
$a = Get-Content -Raw -LiteralPath '.\ACCEPTANCE.json' -Encoding UTF8 | ConvertFrom-Json
if ($a.result -cne 'PASS_BOUNDED_WINDOWS_CANDIDATE' -or $a.package_sha256 -cne $expected) {
    throw '验收记录不匹配，停止。'
}
$out = Join-Path (Get-Location) 'qbrain-n48s'
if (Test-Path -LiteralPath $out) { throw '目标目录已存在；使用新目录，勿覆盖活动安装。' }
Expand-Archive -LiteralPath $zip -DestinationPath $out
Get-Content -LiteralPath (Join-Path $out 'START-HERE.zh-CN.md') -Encoding UTF8
```

EXE 固定 SHA256：`c65f3e8e9e08d7ccf43c245193829af9334f0dfa19f00c447a713a0a243d879d`。
默认 SQLite 已在只保留系统路径的原生 CI 中执行，不要求单独安装 PostgreSQL/额外启动
DLL 或 Python；PG 模式仍需要可信数据库客户端依赖，可能包含相应 VC 运行库。
不要把早期单模块文档的通用依赖说明误用为此固定 EXE 的实测依赖结论。
这不是签名稳定版，也没有在用户电脑执行过上述命令块。

项目安装、备份、停用及独立权限开关按包内 START-HERE 和对应说明操作。先备份再升级；
不要删除 WAL/SHM 来绕过错误，不要把真实 DSN/密码或脑库内容上传到公开仓库。

## 源码补充与可复核结果

新离线复核器和反例测试以候选 `9f9c34017cbc3c2ab787f145059e847f7b2cb8c3` 为基线，
只增加审核/文档，不改 C++、安装器、旧测试或原生包。补丁不适用于旧 main；应用之前
核对基线，执行 `git apply --check`。本轮已在干净的候选源树上实际验证补丁应用。

提供原始 Windows 工件解压目录和原 portable `source.zip`，在补充源码根目录执行：

```text
python tools/delivery/review_n48s_outcome.py --evidence <Windows工件目录> --canonical-source <portable/source.zip> --output <新结果.json>
python tools/delivery/test_review_n48s_outcome.py --evidence <Windows工件目录> --canonical-source <portable/source.zip> --result <新测试结果.json>
```

这只是离线回读，不会运行 Windows EXE 或连接 PG；不把它当成新增本机原生测试。
该校验器故意绑定这一个固定包、源码树、原 CI Runner 与解释器路径及全部 27 条验收命令，
不接受任意新版本或新运行环境自动继承旧结果。修复前版本存在命令校验缺口，
已新增完整 argv 绑定和 53 个反例；使用本次修复后源码，勿沿用旧复核器的 PASS。

结果 `PASS_FIXED_ARTIFACT_TOP_LEVEL_READBACK` 只适用于固定工件和 27 个顶层验收命令。
嵌套 55 步及各报告的全部命令 argv 未逐项重建，修改未绑定嵌套 argv 仍可能通过回读；
嵌套证据仅按审核报告列出的身份、摘要及选定语义检查复核。结果中的
nested_command_binding_verified 和 descendant_execution_verified 均为 false。
不要把此结果解释为所有后代命令或业务行为都被独立证明执行。

PR61 当前仍草稿；补充代码需经修复后独立复审与远端提交核对，不把本地交付等同
已推送、已合并或全部结项。真实客户端消费、实际模型实验、其余既定要求和正式发布仍独立保留。
