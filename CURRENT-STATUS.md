# Qbrain 当前状态

## N48P：PostgreSQL 分层上下文与摘要缓存

2026-09-29。固定受测提交 `136a4828ec31eeb5d870b3a3814d5b5c533783d6`，
树 `557fe883fa403c86eddd02567cb13248ba82aec6`，基线 main `17a9998f`。
实际合并见 PR58；收尾文档／已执行独立审核源码不冒充程序构建来源。

现有 context list/read/summary 及 MCP context_read/context_write 已有 PG 路径。
保留 L0/L1 预览、UTF8 原文 L2 分页、正文版本、来源／命名空间及写默认拒绝。
PG 单次读取固定快照；摘要回调后重核证据和许可；四类页面变化清除派生缓存。
不重复开发 N48O，也不新增自动置信度或事实覆盖功能。

## 已执行与自审

专项36512018075的Windows/Linux均完成。每平台198原生检查（68 SQLite、130 PG），
每Python模式55次记录调用（42产品、13psql）／173检查通过，旧原生与55步回归保留。
本轮另写完整输出复核器和实际进程探针，不导入原测试／产品辅助函数；原始正文、
版本、分页、MCP拒绝和清除后的缓存全部独立核对。详细完成结果以审核与索引为准。

新鲜本地编译原上下文37项、新SQLite部分68项通过；ASan/UBSan下68项通过且无诊断。
每种模式独立33次实际调用／87检查通过。没有本地PG服务器或用户电脑执行。
当前已审范围未发现遗留阻断问题；本人分离自审不是第三方认证或绝对无缺陷保证。

[操作说明](docs/integration/POSTGRES-LAYERED-CONTEXT.zh-CN.md) ·
[结果审核](docs/nodes/N48P-HARD-AUDIT.md) · [精确结果](docs/nodes/n48p-evidence/RESULT.json)。

## 范围边界

SQLite仍默认；PG同一DSN不同brain标签不是硬租户隔离。输出预算不等于模型token预算。
目录最多256页／16MiB已选正文，单页16MiB，外部模型需单独授权。新EXE未签名，需相应
VC运行库；PG另需可信服务器/libpq。旧固定ZIP与公开Release未替换。

fact_store/Hook等剩余PG模块、真实客户端消费、真实模型效果/全流程费用、完整DLP/RLS、
签名稳定版和Issue40继续独立保留。[上一状态](CURRENT-STATUS-N48O.md)。
