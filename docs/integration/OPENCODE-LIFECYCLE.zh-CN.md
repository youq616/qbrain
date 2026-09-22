# OpenCode 项目配置完整生命周期（N48E）

本模块将此前 N48A/B/C 的安装、只读审计、恢复和外部编辑接管整合为原生
`qbrain opencode` 命令。需要含 N48E 的源码构建；现有 N47X 公开包不含这些命令。
只管理指定项目的配置与 Qbrain 归属记录，不修改全局 OpenCode 配置，不自动采集会话。

## 先明确客户端版本，不自动猜测格式

实际验证的宿主为 **OpenCode 1.18.31**，Windows/Linux 都有无账号配置加载与 MCP
连接证据。使用该版本时明确选择 `--format v1`。V1 使用 `mcp.<name>`、`enabled`
及整数型 timeout。V2 使用 `mcp.servers.<name>`、`disabled` 及阶段 timeout 对象。

本模块可以按 V2 格式生成、管理、撤销配置；但本阶段没有运行原生 V2 引擎。
1.18.31 的兼容读取可以连接该 V2 条目，却省略本模块的 V2 startup/catalog 超时对象。
所以“V1 兼容读取 V2 并连接成功”不等于“V2 语义完整支持”。不要对 1.x 客户端选择
v2 再推定其超时设置生效。本次保持原格式定义，没有暗中改写配置去伪造等价性。

## 安装和明确的写权限

在 PowerShell 中先设置已存在项目、已核验程序和脑库名称，再预览。以下为接口
使用示例，不表示已经在用户本机执行。所有路径应指向实际对象。

```powershell
$ErrorActionPreference = 'Stop'
$exe = (Resolve-Path 'C:\Qbrain\qbrain.exe').Path
$project = (Resolve-Path 'D:\Projects\MyProject').Path
$brain = 'my-brain'
$argsForProject = @('--project', $project, '--format', 'v1', '--binary', $exe, '--brain', $brain)
& $exe opencode preview @argsForProject
```

检查预览的项目选择、格式、`write_enabled`、服务器名称和 `would_change`，再将实际
`plan_sha256` 填入明确执行命令。预览不会启动宿主或初始化默认脑库。

```powershell
& $exe opencode install @argsForProject --approve-sha256 '<预览返回的plan_sha256>'
& $exe opencode status --project $project
& $exe opencode audit --project $project --expect-format v1 --expect-access read-only
```

默认配置固定为 `serve --brain <brain> --tool-profile memory`，并将环境中的
`QBRAIN_MCP_ALLOW_WRITE` 设为 `0`。只有在预览与安装中都显式传入 `--allow-write`，
命令才增加写许可。重新安装时省略此选项就恢复只读，不能用原读权限计划执行写配置。
工具可见不等于可写；被调用工具仍受 Qbrain 原有来源与权限规则限制。

## 状态和审计不等于宿主已经使用

`status` 检查受管文件是否和归属记录一致，并报告待恢复状态与已知配置覆盖层。
`audit` 只读核对项目文件、归属、程序摘要、权限预期和祖先配置存在性。它不读取全局
或远程配置，不启动 OpenCode，不证明最终合并配置、模型采用记忆或完整可执行安全性。
审计成功退出码为 0，未通过为 1，非法审计参数为 2。

审计结果为 `LOCAL_REGISTRATION_CHECKS_PASSED`、`NOT_REGISTERED`、`BLOCKED` 或
`UNVERIFIABLE`。不能把不可验证解读为安全或未安装，也不要根据此报告自动清理。
普通变更与预览命令失败时返回固定错误码，不输出配置正文。

## OpenCode 自动补写 schema 的处理

实际 OpenCode 1.18.31 会在无 `$schema` 的文件中补写 schema 注释字段，包括
`debug config`／`mcp list` 等加载操作。因此不能把这些宿主命令统称为文件系统只读。
Qbrain 发现字节变化后会报告 `configuration_matches=false`；普通更新或卸载预览
会拒绝 `opencode_external_edit`，不会为卸载而覆盖宿主或用户改动。

经检查，受管 Qbrain 条目本身未改变且只有可保留的外部编辑时，可以先预览接管：

```powershell
& $exe opencode reconcile-preview --project $project
```

确认后另行执行，再检查状态：

```powershell
& $exe opencode reconcile --project $project --approve-sha256 '<接管预览的plan_sha256>'
& $exe opencode audit --project $project --expect-format v1 --expect-access read-only
```

接管只处理原归属记录对应的条目，保留无关服务、其他设置、注释及周围原始字节，
并把它们作为新的撤销基线。受管命令、脑库、工作目录、环境、超时或权限有变化时
拒绝接管。它不自动认领任意服务器，也不能用来间接提升写权限。

## 卸载和中断恢复

正常卸载同样先预览、再明确批准：

```powershell
& $exe opencode uninstall-preview --project $project
& $exe opencode uninstall --project $project --approve-sha256 '<卸载预览的plan_sha256>'
```

撤销配置不删除脑库；被明确接管的外部编辑会保留。已经存在待恢复日志时，不应删除
日志或强行重装，应先检查恢复计划：

```powershell
& $exe opencode recovery-preview --project $project
& $exe opencode recover --project $project --approve-sha256 '<恢复预览的plan_sha256>'
```

恢复核对日志前后镜像、配置/归属对应关系和暂存文件。只接受已知状态，未知修改、
不完整暂存、链接或身份变化会拒绝，不强删或静默猜测应保留哪个版本。发生冲突后
保存证据，在可信副本中检查；不要将本说明理解为授权批量删除用户文件。

## 数据保留与范围

配置采用 JSONC 有界解析，保留未修改部分的字节，包括注释、BOM 和换行。写入使用
逐文件原子替换、合作锁、写前日志及每次写前复核，**不是跨两个文件的原子事务**，
也不是排除所有检查到替换之间竞态、敌意管理员、恶意触发器或物理断电的保证。

归属记录与恢复日志位于 Qbrain 数据根下的 `integrations/opencode/<project-id>/`。
它们可能包含配置的完整原文/前镜像，可能有私人资料，不能当作脱敏审计结果上传。
Windows 拒绝大小写敏感、链接及无法验证的相关路径；这不是自动迁移支持。

本次实际宿主检查没有发送模型提示、调用 MCP 业务工具或使用个人凭据。
真实记忆消费、质量/费用、其他版本宿主、PG 对等和签名验收仍分别需要完成。
[完整工程自审](../nodes/N48E-HARD-AUDIT.md)与[证据摘要](../nodes/n48e-evidence/SUMMARY.json)
区分了原生配置管理测试、真实宿主连接测试与尚未执行的项目门槛。
