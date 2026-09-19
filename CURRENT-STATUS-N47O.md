# Qbrain 当前交付状态

## N47O：集成 Windows 预览交付完成

2026-09-19（Asia/Seoul）。[windows-preview-c26ec5e5](https://github.com/youq616/qbrain/releases/tag/windows-preview-c26ec5e5)
已公开，包含已审核的 N47M/N47N 修复。此前“源码已修复、公开包仍旧”的缺口已关闭。
本阶段为交付工程，不新增应用功能、数据库迁移、默认采集许可或用户本机改动。
仍是未签名、非 latest 的开发预览，不是项目全部完成。

## 下载入口和固定身份

下载 `qbrain-windows-x64-reviewed.zip`，先读同版本 `START-HERE.zh-CN.md`。
[仓库内安装说明](docs/integration/REVIEWED-PREVIEW.zh-CN.md)提供校验、解压、升级、
项目安装和卸载命令，默认不采集；不需要本机编译器、Docker/WSL/Python 服务。
同一 Release 另有 SEARCH-ARGUMENTS、PROVENANCE、SHA256SUMS 与原始验证证据 ZIP。

| 对象 | 身份 |
| --- | --- |
| 实际原生测试源码 | `c26ec5e512d9ba960b86c9ced5b9b4976b031f2c` |
| 产品源树 | `2beda65c13421a995826c147aad606ea48d7f694` |
| 产品审核 / 合并 | `65b118542187f2c61895a62f3753d268fab423bf` / `b099c7fb7c8bcd29b5ad40e78a113bbbe82d920a` |
| 发布工具修复与只读核验提交 | `4c1362aee78a3f08dec902ac2e0dad77230c6f2e` |
| 实际发布提交 | `5ec33dd5fefc06a393c0f101139380c0b47ff1f9` |
| 只读通过运行 | [35410946324](https://github.com/youq616/qbrain/actions/runs/35410946324) |
| 发布及匿名下载通过运行 | [35411136813](https://github.com/youq616/qbrain/actions/runs/35411136813) |
| Release ID | `391866783` |

产品 ZIP 为 2,117,939 字节，SHA-256
`ec681a4599bf1b2a90f3848f5bf65b6d6a32e37254f32392d0709c43080b356c`；包内 EXE
为 4,077,568 字节，SHA-256 `c35fadde8c8356b7243bf0b34cfd5c836bda27bb46da87eddcc79c1031bf05b5`。
与 c26 N44 inner ZIP 逐字节相同，只改变下载名称。旧包内文档保留，新增旁附说明
明确此次版本。发布提交和最终文档提交不能替代实际构建源码。

## 本轮实际验证与自审

重新查询固定 N47N/N42/N44/清单运行和 11 份原始工件。原验证器完成 1,216 项
核验，覆盖 1,005 个源码文件和 73 项包清单；两平台 N47N 原始报告交叉核对各
1,746 项。这是重新核验已有原生证据，不是重新执行用户真实 Windows 客户端。

发布状态机 14 项测试方法及新增传输 2 项方法在普通/优化 Python、当地环境和
实际 CI 均通过；匿名下载步骤另有 4 项模拟边界检查。公开前后六个资产全部下载
并逐字节比对，固定同一组 ID/size/digest；公开后又无令牌匿名下载六个资产成功。
本会话再次下载发布工件、检查 20 个成员、来源/回执/校验和及 ZIP/EXE 一致性。

**审核结论：N47O 限定交付范围 PASS，未发现未解决的阻断问题。** 审核由协调者
本人另行进行，属于用户授权分离工程自审，不冒称其他代理或第三方认证，不保证
绝对无缺陷。第一轮只读 CI 在工件下载失败，修正请求 Accept 和错误记录后重新
通过；历史失败保留，没有放宽原始哈希或验收断言。

[最终自审](docs/nodes/N47O-HARD-AUDIT.md) ·
[发布回执](docs/nodes/n47o-evidence/RELEASE.json) ·
[匿名下载回执](docs/nodes/n47o-evidence/PUBLIC-READBACK.json) ·
[PR #32 合并状态](https://github.com/youq616/qbrain/pull/32)。
收尾将工作流恢复为已通过的只读版本；实际合并身份以 PR 回执为准，不预称新 CI 通过。

## 项目阶段和剩余回合

当前处于“核心工程预览已公开，向日常使用 v1 验收收口”的阶段。
按本次交付后计算：日常可用 v1 预计 4–6 个实质回合；现有完整扩展路线预计
15–25 个回合（包含 v1），条件是范围不继续扩大、必要宿主/模型/数据库测试条件
可用且无重大返工。估计不是承诺，也不能用大量测试次数替代业务完成度。
[完成标准、工作分解和条件](docs/COMPLETION-ROADMAP.md)。

下一优先项为真实使用、故障恢复和最终效果验收，避免无限扩大参数修补或重复发布。
PG 对等、完整 ACL/DLP、通用语义整理、确认/衰减/画像、更多宿主、完整质量费用和
正式签名仍属未完成范围。没有新增真实 PG、登录客户端、模型消费或外发验收。
当前无需用户本机操作；确需本机时仍只给一个完整提示词并先发布所需文件。

[N47N 原状态](CURRENT-STATUS-N47N.md)及更早状态按原字节保留为历史。
