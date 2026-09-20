# Qbrain

Windows 原生 C++20 / PowerShell 记忆与知识库，默认 SQLite + FTS5。
应用不需要Docker、WSL或Python服务；可选模型评测工具需要Python3.10+。

## 当前公开下载：N47X 当前源码集成预览

**[下载 windows-current-preview-b810d689](https://github.com/youq616/qbrain/releases/tag/windows-current-preview-b810d689)**

选择 `qbrain-windows-x64-n47x-preview.zip`，同时取得同版本 `SHA256SUMS.txt` 并先读
`START-HERE.zh-CN.md`。PROVENANCE记录来源；VALIDATION-EVIDENCE保留原始验收工件。
不要把GitHub自动生成的Source code压缩包当作程序包。

产品ZIP：**4,327,611字节、27个成员**。SHA256：
`c517582c1ea0e0795e881155edd4d34288e3a002dc3bc7657dafcb96a1eb8b4d`。

本次由固定产品源码b810d689重新编译EXE，包含N47S模型对照、N47T/U使用回执与
逐条审计、N47V安装路径保护和N47W桥接诊断，补齐了此前源码与下载包的差距。
仍是**未签名、非latest开发预览**，不是稳定版。继承内部版本2.0.0不代表稳定验收；
以发布标签、来源和EXE哈希识别具体构建。[当前状态](CURRENT-STATUS.md)。

## 安装和升级

[完整校验、安装与升级说明](docs/integration/CURRENT-PREVIEW-N47X.zh-CN.md)提供可复制
PowerShell命令。升级前关闭相关进程、备份数据，解压到新目录，不覆盖旧程序目录。
用新安装器/EXE对原项目和宿主重新安装，保持原脑库ID。默认不开采集、事实整理或
召回；重装未重传的开关会关闭，不推定旧许可继续生效。不要绕过客户端信任或杀毒。

旧[N47R发布](https://github.com/youq616/qbrain/releases/tag/windows-integrated-preview-9e9a92b0)
及其资产保持不变；历史节点中“仅源码可用”的描述是当时状态，当前N47X已集成上述功能。

## 能力与边界

事实保留完整原话和来源，支持显式生命周期操作。使用回执可上报、撤回、按版本汇总
和分页审计；它仍是调用方陈述，不证明模型采用或事实为真，不自动改变排名/衰减。
[上报撤回](docs/integration/FACT-USAGE.zh-CN.md) · [逐条查询](docs/integration/FACT-USAGE-AUDIT.zh-CN.md)。

安装器拒绝大小写敏感或无法验证的相关目录，不迁移ID或修改目录标志。
[路径限制](docs/integration/CASE-SENSITIVE-PATHS.zh-CN.md)。桥接阶段诊断不含原话或参数，
默认10秒不提高；[诊断说明](docs/integration/TRANSPORT-DIAGNOSTICS.zh-CN.md)。
[Issue40](https://github.com/youq616/qbrain/issues/40)历史超时根因仍未知，未因发布关闭。

模型对照工具支持离线计划、明确授权的API请求和原始回答评分；密钥只在本机。
[模型工具](docs/integration/MODEL-COMPARISON.zh-CN.md) · [任务评测](docs/integration/TASK-EVALUATION.zh-CN.md)。

## 已验证交付，不代替真实效果

新原生构建和原60注册组通过；包内75使用检查、71分页检查、48模型工具测试及原有
进程回归完成。两版PowerShell各49旧版升级检查、84路径检查及原安装恢复套件通过。
两种事件格式各50任务/520调用；100次HTTP使用明确的测试响应器，不是实际模型。
五项发布资产均完成公开前后字节比对与无令牌下载核验。
[本人分离自审](docs/nodes/N47X-HARD-AUDIT.md) · [精确证据](docs/nodes/n47x-evidence/SUMMARY.json)。

真实登录客户端消费、实际模型效果/费用、PostgreSQL新模块对等、语义确认/画像/
衰减、完整ACL/DLP、规模性能及签名仍有未完成项。当前v1约3–4、完整路线约15–25
实质回合（包含v1）的估计有条件且非完成承诺。[完成路线](docs/COMPLETION-ROADMAP.md)。

## 源码

构建使用scripts/build-cl.ps1和scripts/build-tests-cl.ps1；只有同轮生产构建成功且
源码未变才使用-SkipProductionBuild。本机确需任务时遵循[单提示词交接](LOCAL-AGENT-HANDOFF.md)。
[LICENSE](LICENSE) · [第三方说明](THIRD-PARTY-NOTICES.md) · [规范操作清单](docs/OPS-PARITY-LEDGER.md)。
