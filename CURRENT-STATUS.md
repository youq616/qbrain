# Qbrain 当前交付状态

## 已合并并发布：N47K 只读诊断查看

[PR #27](https://github.com/youq616/qbrain/pull/27) 已合并，产品合并提交
`bff8bff5a45f71b857e363bf6d50fda3e3473f4a`。实际产品／原生测试源码为
`a23800df3709ac9ef73a51d150b64d2d20d7d21f`，源树
`b95af421ea5ebb756a127fe8cc519b5b62e17cf6`。
审核头1400018a相对产品只增加/更新docs下8个计划和审核证据路径，未改变生产代码、
原测试、产品构建或包字节。合并提交与审核头无文件差异。

[预览 Release：diagnostics-preview-a23800df](https://github.com/youq616/qbrain/releases/tag/diagnostics-preview-a23800df)
已公开。产品 `qbrain-windows-x64-diagnostics.zip`，2,091,494 字节，SHA256：
`6f35d1cb1eccb4cdab727963ae45ba805dbc9edfa0c5867472aa62b992b35bb3`。
完整解压并阅读 `HOOK-DIAGNOSTIC-INSPECTION.zh-CN.md`。原CI字节，未重打包、未签名，
不是整个融合项目的最终发行；运行预编译包不要求本机编译器。

## 新增的本地排查入口

`qbrain hook diagnostics --config <绝对配置路径>` 只读该host的五个固定N47J诊断槽，
可按固定事件或精确session-key筛选。不打开脑库、不触发Hook、不创建锁或目录、不
调用模型，也不新增MCP本地文件读取入口。普通Hook和所有安装默认开关保持。

返回INSPECTED以及present/missing/invalid/unreadable/unsafe_path/oversized/
session_mismatch。严格验证完整元数据；无效记录不回显原文、异常文字或路径。
不读取任意记录、不回退last-trace或tmp；配置关闭仍可查看历史，但不代表目前启用。

INSPECTED/present不是模型消费、真实性、安装健康或新鲜度证明。单配置64KiB、记录
4096字节、最多五槽、响应32KiB。各文件独立观察，不是原子快照；静态link/reparse
检查不保证抵御敌对目录竞争或硬链接。读取可能影响OS atime，不能承诺零系统副作用。

## 修复与已执行验证

初始e9d8f3e1真实Windows构建因两处显式链接清单漏diagnostics.obj而失败。修复版
补齐生产和全测试链接，并加10项默认源/对象闭合检查；原失败与证伪记录保留。
这不是用户缺少工具链，也未用CMake通过替代原生链接验证。

修复运行35186099196与35186099174必需任务全部完成成功：完整Windows59注册组、
最终打包、Server2022、portable及Linux ASan/UBSan通过。新诊断单元各11场景107断言；
真实CLI各60检查68命令（54预期exit0、14预期exit2）。全部既有事实、记忆、Hook、
严格JSON、生命周期、HTTP/队列/CJK及双PowerShell门槛保留。真实PG DSN仍SKIP-PG。

本轮单独工程自审从866文件原始源码重新GCC14.2构建，诊断11/107、60/68、旧trace
9/169、66/80及原Hook69检查通过；204项报告/注册测试和40命令160断言独立CLI检查
通过。新检查覆盖完整规范记录、损坏与敏感字段、精确字节边界、不回退旧记录、
会话筛选及内容/mtime/拓扑不变。历史检查点的大型探针不重复计入本轮。

6个原始工件、全部70包成员及完整源树/原报告/脚本/EXE等318项回读通过。审核无
本阶段未解决P0/P1，不保证不存在所有潜在缺陷；按所有者授权单独自审，不冒称
第三方或真实子代理。诊断探针EXE未另下载，身份依赖固定原报告及原CI实际文件核验。

发布35198816028成功：核对固定产品、审核、已合并PR和原CI，重复318项检查，先上传
新草稿、下载逐字节比对三个资产再公开。发布核验报告已另下载，其字节与本地报告
完全一致。无重编译/重打包、覆盖旧Release或开启通用未审核自动发布。

[阶段审核](docs/nodes/N47K-HARD-AUDIT.md) · [测试摘要](docs/nodes/n47k-evidence/SUMMARY.json) ·
[发布记录](docs/nodes/n47k-evidence/RELEASE.json)

## 保留能力与未完成范围

N47J分事件记录和forgotten重放修复、严格JSON、候选分页、原子批量归档/恢复、只读
证据年龄、明确开启的本地规则整理/事实Hook、证据生命周期与含反证召回均保留。
没有新采集/外发许可、数据库迁移或真实Claude/Codex会话验收，不修改Codex认证。

自动语义合并/冲突推断、使用/确认计数、自动衰减、画像、PG对等、完整ACL/DLP、
模型质量/费用与正式签名仍未完成。阶段完成不等于整个项目完成。
当前无需本地Agent接手或重复N47E验收，不需Token、额外GitHub权限、编译器或再次
导出源码。真正本机任务仍只给一个完整提示词，所需文件先放仓库并固定来源与用法。
