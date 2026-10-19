# Qbrain 当前状态

## N48R：PostgreSQL Hook 模块完成限定源码验收

2026-09-30（Asia/Seoul）。主分支基线N48Q b4793e2a。
原运行受测45a238534e67c173b6baa4f2ed257f6117b72044，树00405f2f；
补充独立审核受测a4acb118197ad1205ddce086f83f6461ccedbb06，树faa070dc。
实际合并见[PR60](https://github.com/youq616/qbrain/pull/60)。

已有PG库的Hook准入、错误不回退、事实/会话联合自有只读快照、调用方事务拒绝、
跨数据库普通记忆去重和读取后采集已完成。完整用户证据、来源/角色、撤回抑制、
输出预算及单独授权保留。默认SQLite，不自动迁移或扩张模型/MCP写许可。

原运行36583542753：Windows/Linux原生Hook80（20SQLite、60PG/设置），事实228、
上下文198、会话122、表范围112、核心8组及完整55步；Windows60个必需注册组通过。
新增运行36652734242：双平台新编译、原生Hook80与2组Hook测试通过，每种Python模式
独立SQLite26次调用/70检查，PG58次调用/124检查（38产品、20psql）通过。
本地新编译核心8组、原Hook13场景229检查、新20检查及原进程回归通过；ASan/UBSan
下20+229通过且诊断为空。没有本地PG服务或用户Windows11实测。

原两份工件1528文件及新两份1540文件的SHA/CRC、Gitblob和完整树已独立核对。
原4组报告220次Hook输出完整重建，每组拒绝6种语义篡改；新8组报告1008份原始流、
152次Hook输出和跨库去重序列回读通过。4次旧统一门槛回放完成。
本轮新写独立审核及补充工作流，原运行实现归属已有候选，不冒称重新实现。

首轮补充Windows审核脚本未关闭SQLite句柄，临时目录清理失败；修正资源释放后新运行
完整通过，未忽略错误或修改产品/断言/超时。失败工件及审核驱动错误记录保留。
本人在实现后分离自审：已审范围无遗留阻断问题，不是第三方或绝对无缺陷认证。
[审核](docs/nodes/N48R-HARD-AUDIT.md) · [结果](docs/nodes/n48r-evidence/RESULT.json) ·
[中文说明](docs/integration/POSTGRES-HOOKS.zh-CN.md)。

## 项目尚未全部结项

PG同DSN不同brain不隔离租户；source不是RLS。真实客户端记忆消费、真实模型效果/
全流程费用、其余既定功能、签名稳定版和Issue40仍需各自验收。
没有使用用户脑库或付费模型，没有更换公开发行资产；程序仍未签名并需要VC/libpq依赖。
[上一状态](CURRENT-STATUS-N48Q.md) · [主路线](docs/COMPLETION-ROADMAP.md)。
