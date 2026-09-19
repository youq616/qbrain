# Qbrain

Windows 原生 C++20 / PowerShell 记忆与知识库，默认 SQLite + FTS5。
预编译应用不需要编译器、Docker、WSL 或 Python 服务。Python 仅用于可选评测
和开发工具。gbrain / OpenViking 是设计参考，不表示所有功能完全等价。

## 最新源码功能：N47U 使用回执逐条审计

新增 `fact usage-list --id ID`：按当前/历史/已撤回状态筛选，定位具体回执后再明确
选择撤回。分页受数量和字节预算限制；中途数据变化拒绝旧游标，不混合新旧结果。
查询不新增回执，不改写入权限/Hook/schema；调用方上报仍不等于真实模型消费。
两平台新71项检查、原75项使用记录回归与Windows60组通过，原始证据已回读自审。
[查询与完整分页示例](docs/integration/FACT-USAGE-AUDIT.zh-CN.md) ·
[自审](docs/nodes/N47U-HARD-AUDIT.md) · [当前状态](CURRENT-STATUS.md)。
本功能在新源码中，现有N47R公开包不含N47T/N47U命令，本轮未替换发行包。

## 已有源码功能：N47T 可撤回的事实使用回执

新增 `fact report-use`、`fact revoke-use` 和 `fact usage --id`，可显式上报使用、
幂等重试、永久撤回，并分别查看当前/历史版本计数。只表示调用方声称使用，不证明
模型消费或事实为真；普通读、检索和Hook不会自动记账，也不改变排名或衰减。
SQLite可选模块首次有效写入前备份；最后支持被遗忘后回执随事实删除。
两平台各75项新检查/118命令、原回归及Windows60组通过，本人分离自审已归档。
[使用与容量/恢复边界](docs/integration/FACT-USAGE.zh-CN.md) ·
[自审](docs/nodes/N47T-HARD-AUDIT.md) · [当前状态](CURRENT-STATUS.md)。
**此功能在新源码中，下方N47R旧下载包不含这些命令，本轮没有替换公开发行。**

## 已有源码工具：N47S 受控模型对照

新增离线计划、明确授权的独立HTTP请求和原始回答评分，支持固定任务对照，无需
手工复制答案。最终48方法及Windows引擎→回环HTTP流程已验证；回环响应并非真实
模型效果，账号/客户端验收仍待完成。v2计划隐藏测试会话元数据，保留原话与证据。
[使用说明](docs/integration/MODEL-COMPARISON.zh-CN.md) ·
[该阶段自审](docs/nodes/N47S-HARD-AUDIT.md)。
该工具在仓库源码中，未修改下方N47R发行包。

## 当前下载：N47R 集成 Windows 开发预览

**[下载 windows-integrated-preview-9e9a92b0](https://github.com/youq616/qbrain/releases/tag/windows-integrated-preview-9e9a92b0)**。
选择 `qbrain-windows-x64-n47r-preview.zip`，同时取同版本 `SHA256SUMS.txt` 并先读
`START-HERE.zh-CN.md`。不要把自动生成的 Source code 压缩包当作应用包。

N47R 已把 N47P 安装恢复修复与 N47Q 评测工具纳入同一个经过原生验收的下载包，
不再需要手动拼接旧包与新源码。原 c26 EXE 不重编译，ZIP 重新组装；安装器和
评测工具分别固定来源，85个成员由新清单覆盖。旧 N47O 包和历史说明仍保留。

ZIP：**4,858,530 字节**。SHA-256：
`e7158949d805a0a25157bfb720561e4b21e80a433a6c7f031c60ee3bbaa746c5`。

[安装、校验和升级说明](docs/integration/INTEGRATED-PREVIEW.zh-CN.md)包含可复制
PowerShell 命令。解压到新目录；升级前关闭相关进程并备份数据。默认不采集，
升级未重传的采集/整理/召回开关会关闭。不要绕过客户端信任或关闭防病毒。

本版本仍为**未签名、非 latest 的开发预览**，不是稳定 v1 或全项目完成声明。
内部清单保留构建时 NOT_RUN 状态；外部 PROVENANCE 与验收回执绑定同一 ZIP
的后来测试结果，未通过改写测试包来伪造通过。哈希不是代码签名。

## 已完成的整包验证

Windows PowerShell5.1/7 各24项快照、60项恢复及原安装/许可/传输/事实/整理回归
通过；旧预览到新路径升级各37项通过。包内两种事件格式各50任务与520次原生
调用通过；全新 MSVC 原套件60个注册组逐项核对。五个发布资产均完成公开前后
字节检查和无令牌匿名下载，原始五份验证工件保留在可单独下载的证据 ZIP 中。

这些使用合成数据，不代表新的真实客户端登录或模型效果验收。真实 PG 仍有
SKIP，模型用量/费用未执行的字段保持未知。本人分离工程自审不冒称第三方认证。
[完整审核](docs/nodes/N47R-HARD-AUDIT.md) · [当前状态](CURRENT-STATUS.md) ·
[发布证据](docs/nodes/n47r-evidence/SUMMARY.json) · [PR #35](https://github.com/youq616/qbrain/pull/35)。

## 下一里程碑

当前处于“集成预览已交付，继续完成日常可用 v1 的真实使用与效果验收”。
当前条件性估计：v1还需约**3–4个实质回合**；现有完整增强路线仍粗估
**15–25回合，包含v1**。不是固定日期或次数承诺。本轮事实使用记录功能推进了
完整路线的一部分，不能替代尚缺的真实客户端/模型观测。
[完成标准与剩余工作](docs/COMPLETION-ROADMAP.md)。

真实客户端消费、模型对照与费用、PG新模块对等、通用语义合并/冲突/衰减、
完整ACL/DLP、更多客户端、规模性能和正式签名仍有未完成项。
[评测工具使用](docs/integration/TASK-EVALUATION.zh-CN.md) ·
[恢复边界](docs/integration/INSTALLER-RECOVERY.zh-CN.md) ·
[规范操作清单](docs/OPS-PARITY-LEDGER.md)。

## 源码与历史

源码构建使用 `scripts/build-cl.ps1` 和 `scripts/build-tests-cl.ps1`；仅在同轮
生产构建成功且源码未变时使用 `-SkipProductionBuild`。实际本机任务仍遵循
[一个完整提示词的交接约定](LOCAL-AGENT-HANDOFF.md)，不要上传密钥或私人聊天。
[旧 README](README-BEFORE-N47R.md)保留原字节；其中下载状态是历史。
[LICENSE](LICENSE) · [第三方说明](THIRD-PARTY-NOTICES.md)。
