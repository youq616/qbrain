# Qbrain

Windows 原生 C++20 / PowerShell 记忆与知识库，默认 SQLite + FTS5。
预编译应用不需要编译器、Docker、WSL 或 Python 服务；Python仅用于可选评测与开发。

## 当前源码：N47W 进程桥接诊断

新增固定字段的启动、输入、进程等待和输出排空诊断；默认成功结果不变，失败诊断
不包含路径、参数或正文。输入等待修正为共用启动后剩余预算，默认10秒不提高。
两版PowerShell各29项新检查及原安装回归通过，完整原生60组已核验。本人分离自审
修正了测试清理的PID身份核对，未放宽原测试。Issue40根因仍未知，不声称已经修复。
[当前状态](CURRENT-STATUS.md) · [审核](docs/nodes/N47W-HARD-AUDIT.md) ·
[使用与隐私限制](docs/integration/TRANSPORT-DIAGNOSTICS.zh-CN.md)。
本轮只更新源码，不替换下方N47R公开包。

## 已有源码：N47V 安装路径身份保护

为避免大小写敏感目录中的Project/project共用安装记录，安装器现在保留普通目录
历史ID，并拒绝大小写敏感或无法验证的相关目录。只读原生检查，不修改目录属性、
不迁移安装ID，也不声称完整支持这类路径。默认权限、恢复事务、Hook和程序不变。

两版PowerShell各84项路径检查、22项额外边界审核及所有原安装回归完成；原生60组
通过。一次原Codex Hook启动超时在相同版本复跑中未重现，原因仍未知，保留于
[Issue40](https://github.com/youq616/qbrain/issues/40)，没有把它写成已修复。

[当前状态](CURRENT-STATUS.md) · [N47V自审](docs/nodes/N47V-HARD-AUDIT.md) ·
[不支持路径的处理](docs/integration/CASE-SENSITIVE-PATHS.zh-CN.md)。
本轮不发布新包，下面的N47R安装器不含本次检查。

## 已有源码功能

N47T提供事实使用上报、撤回和版本隔离汇总；N47U提供逐条审计及数据变化检测分页。
调用方上报不是实际模型消费或事实真伪证明，不自动改变排序、画像或衰减。
[上报/撤回](docs/integration/FACT-USAGE.zh-CN.md) ·
[回执查询](docs/integration/FACT-USAGE-AUDIT.zh-CN.md)。

N47S提供离线模型对照计划、明确授权的API执行和原始回答评分，真实模型/客户端
效果仍待实际观察。[使用说明](docs/integration/MODEL-COMPARISON.zh-CN.md)。
这些源码能力尚不属于下方N47R公开包；源码完成不等于公开二进制已经更新。

## 当前公开下载：N47R Windows 集成开发预览

[windows-integrated-preview-9e9a92b0](https://github.com/youq616/qbrain/releases/tag/windows-integrated-preview-9e9a92b0)。
选择qbrain-windows-x64-n47r-preview.zip，同时获取同版SHA256SUMS、PROVENANCE和
START-HERE说明，不要把Source code归档当程序包。旧Release/tag保持原样。

ZIP为4,858,530字节，SHA256：
`e7158949d805a0a25157bfb720561e4b21e80a433a6c7f031c60ee3bbaa746c5`。
该版本整合N47P恢复修复与N47Q工具，仍为未签名、非latest的开发预览，不是稳定v1。
[该版本安装/升级说明](docs/integration/INTEGRATED-PREVIEW.zh-CN.md)。

## 剩余工作、构建与历史

核心预览已交付，真实客户端使用、模型对照与费用、PG新模块对等、语义确认/画像/
衰减、完整ACL/DLP、其他宿主、规模性能及签名仍有待完成范围。
现有估计：v1约3–4个实质回合，完整增强路线15–25且包含v1；必要环境可用、范围
不扩大且无重大返工为前提，不能按消息次数倒数。[完整路线](docs/COMPLETION-ROADMAP.md)。

源码构建用scripts/build-cl.ps1及scripts/build-tests-cl.ps1；只在同轮生产构建成功且
源码未变时使用-SkipProductionBuild。本机确需交接仍遵循[单提示词约定](LOCAL-AGENT-HANDOFF.md)，
不要上传密钥或私人聊天。[上一README](README-N47U.md)保留历史字节。
[LICENSE](LICENSE) · [第三方说明](THIRD-PARTY-NOTICES.md) · [规范清单](docs/OPS-PARITY-LEDGER.md)。
