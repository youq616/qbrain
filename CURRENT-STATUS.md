# Qbrain 当前交付状态

## N47A：代码、独立审核和原生验收已完成

实际代码与两份独立审核对应提交：`cccdacb61e63c29f8b9eaba1c38fbeed3e23e54b`。
源树：`a15a91f7172622e2c8021403d84e63bf36f59147`。
[PR #14](https://github.com/youq616/qbrain/pull/14) 的实时状态表示是否已合并。
本阶段的代码与原生测试保持不变，随后只补入审核原件和验收文档。

实际新增 C++ FactStore、本地 fact CLI，以及既有 memory_read(view=facts) /
memory_write(fact_*动作) 的显式创建、同原话证据附加、撤回、替代和矛盾关系。
保留旧 facts 表；普通读取不初始化，首次有效显式写入先备份再建立独立可选模块。
事实内容取自已提取完整用户原话，confidence=null，不推断真实性或改写否定。
来源、到期、篡改、遗忘和版本规则保持；不会自动改变 Hook 召回或开启模型外发。

[独立审核 A](docs/review/n47a-cccdacb6/review-A.md) 与
[独立审核 B](docs/review/n47a-cccdacb6/review-B.md) 原文已逐字节归档，均 PASS。
13 项非阻塞 P3 保留在 [Issue #16](https://github.com/youq616/qbrain/issues/16)，
不宣称全部修复。审核为源码审查与部分 Python/SQL 实验，原生验收是另外的 CI 证据。
无需重新上传旧 ZIP、补调用文件或重复本地审核。

[开发验证34788803379](https://github.com/youq616/qbrain/actions/runs/34788803379) 与
[N42验证34788803239](https://github.com/youq616/qbrain/actions/runs/34788803239) 必需任务通过：
49组原生回归、事实15场景/380断言、34项CLI/MCP/118次符合预期退出码的命令，
以及既有CJK、队列、Embedding、记忆、Hook、双PowerShell及Server2022 HTTP。
产品仍是未签名开发版。下载/发布状态以仓库 Release 为准，不用历史 dist 代替。

[完整阶段验收](docs/nodes/N47A-HARD-AUDIT.md) ·
[审核接收哈希](docs/review/n47a-cccdacb6/RECEIPT.json) ·
[既有原生证据](docs/nodes/n47a-evidence/DELIVERY-CHECKPOINT.json)。
旧检查点中的“原报告未收到”是当时状态，本次接收记录已取代该项阻塞。

## 已交付 N46F

中文 search、HTTP共享会话修复及 [cjk-preview-c665cb29](https://github.com/youq616/qbrain/releases/tag/cjk-preview-c665cb29)
保留；旧包不含N47A。不要用固定旧464045e2摘要的N46E工具验证新包。
[原N46F记录](docs/nodes/N46F-HARD-AUDIT.md) 不回写为新版本测试。

## 未完成范围

N47后续语义提取、自动冲突判断、衰减/排序、画像和自动事实召回仍需开发。
真实 PostgreSQL 对等、完整应用权限审计、真实模型质量/费用、Codex 已登录宿主
闭环与正式签名发行仍未完成。N47A完成不等于全部融合项目完成。

每阶段完成后要求真实独立子代理审核；不将父代理自查或CI当作子代理。
本地交接始终只给一个完整提示词，文件先进入仓库，指定固定下载、校验与用法；
只委托确需本机的工作，不让本地并行重写仓库修复。
