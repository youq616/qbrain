# Qbrain 当前交付状态

## 已合并并发布：N47B 成对冲突读取

产品合并提交：`42f6dac5be3bf411dac802280b08c828a5a90fbb`，
[PR #17](https://github.com/youq616/qbrain/pull/17) 已合并。
实际代码/原生测试/阶段复核源码：`7999d39b9e6a253d62557a6ccc8341598ccdebb6`。
后续审核和交付文档没有改变该产品代码或测试包字节。

[仓库预览 Release：conflict-preview-7999d39b](https://github.com/youq616/qbrain/releases/tag/conflict-preview-7999d39b)
已发布。文件 `qbrain-windows-x64-conflicts.zip`，1,924,291 字节，SHA256：
`ceb1ad45109a1cdf7a5f72a4982465613ac4119c479025f6e45b139f01014e0c`。
完整解压并阅读 `CONFLICT-INSPECTION.zh-CN.md`。仍是未签名开发预览版。
无需本机安装编译器；旧 N46E 固定哈希入口不接受这个新包，不应绕过校验。

N47B 新增 `fact conflicts` / `memory_read(view=conflicts)`，成对返回已明确声明的
矛盾双方及完整原话、当前 revision、证据来源。只返回 active 且双方证据均有效的
关系；不会自动认定矛盾、选择胜者、篡改原话或自动写入。

一次查询中的双方共用同一个 SQLite 读快照：如果另一个连接在查询期间提交遗忘，
当前查询仍可能返回原快照中的完整对，下次查询观察遗忘。预算不足时不返回半对；
空数组且 truncated=true 不表示不存在冲突。未初始化时读取不建表或备份。

原生运行 34798495285 与 34798495355 必需任务通过：50 个 Windows 注册组，
Server2025/Server2022/portable 各13个冲突场景与346断言，Windows/portable 各38项
CLI/MCP检查与75次符合预期退出状态的命令。旧N47A、HTTP、队列、CJK、记忆、Hook
和双PowerShell门槛保留；真实PG DSN明确跳过。

协调方重新编译原源码并执行Clang ASan/UBSan冲突专项（Linux），通过13/346单元及
38/75进程检查；另有58项报告门槛及134项源码/原始日志/交付回读。阶段审核是所有者
授权的单独工程自审，不是独立子代理或第三方审核。N47A原始子代理报告保持原样。

发布运行34848310013先核对已合并审核头、原始测试任务与固定包/日志摘要，完整
重验冲突及事实单测/进程报告，再上传新草稿、下载比对三项资产后公开。不重编译、
不重打包、不覆盖旧Release、不启用通用未审核自动发布。

[阶段复核](docs/nodes/N47B-HARD-AUDIT.md) ·
[测试摘要](docs/nodes/n47b-evidence/SUMMARY.json) ·
[发布记录](docs/nodes/n47b-evidence/RELEASE.json)

## 已有基础

N46F：中文连续字串搜索补充与WinHTTP会话可靠性。
N47A：完整原话与证据绑定的事实存储、创建/追加证据/撤回/替代/显式矛盾关系。
N47A首次明确事实写入会备份并初始化可选表；N47B没有新增数据库迁移。
基础会话采集、原文记忆、来源隔离、遗忘、MCP、项目Hook和可撤销安装保持。

## 尚未完成

自动语义提取与冲突判断、自动事实召回、衰减/画像、真实模型质量/费用、PostgreSQL
对等、完整ACL/DLP、真实Codex客户端闭环及正式签名发行仍未由本阶段完成。
N47B完成不等于整个N47或整个融合项目完成；既有N47A的P3观察仍逐项跟踪。

当前没有必须由本地Agent执行的新任务。不用重复导出、安装编译器或配置GitHub写
权限。需要实际本机任务时只给一个完整提示词，文件先发布仓库并提供固定来源、
摘要和用法，遵循LOCAL-AGENT-HANDOFF.md，不让本机并行重写相同代码。
