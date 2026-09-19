# Qbrain 当前交付状态

## N47N：Search 字面查询与收尾修复已通过源码验收

2026-09-19（Asia/Seoul）。本次以修正后的 `c26ec5e512d9ba960b86c9ced5b9b4976b031f2c`
为验收对象；[PR #31](https://github.com/youq616/qbrain/pull/31)记录实际合并状态。
**不新建或替换 Release/tag；旧 N47L 下载包仍不含 N47M/N47N 修复。**

支持 `search --query VALUE`、`--query=VALUE` 和 `[options] -- literal words`。
查询中的选项文字不会改写脑库、输出标志或重排参数。未知、重复、缺值、混合形式、
空查询、错误 limit/mode 在开库前拒绝；普通合法输入保留原行为。字面边界不改变
底层分词、排名、来源权限或模型许可，也不保证纯标点必有命中。
[完整语法](docs/integration/SEARCH-ARGUMENTS.zh-CN.md)。

## 已修正的收尾问题

之前 f2ba 的文档收尾将规范操作清单替换为归档链接，导致后续完整 Windows
测试失败；a587 的旧通过结果不能覆盖这个新失败。现已恢复原清单精确字节，
保留失败版本，并补上静态预检和换行/BOM 回归。原生断言与冻结清单未削弱。
状态页及审核索引现统一引用 c26 的新证据，不再引用旧候选作为最终结论。

## 固定源码与实际验收

| 对象 | 身份 |
| --- | --- |
| 基线 main | `b530f361dc9c36cf23127cc2f3c584f3215fb890` |
| 验收源码 | `c26ec5e512d9ba960b86c9ced5b9b4976b031f2c` |
| 验收源树 | `2beda65c13421a995826c147aad606ea48d7f694` |
| N47N 专项 | [35368994138](https://github.com/youq616/qbrain/actions/runs/35368994138) |
| N42 完整验证 | [35368994139](https://github.com/youq616/qbrain/actions/runs/35368994139) |
| N44 完整验证 | [35368994091](https://github.com/youq616/qbrain/actions/runs/35368994091) |
| 静态清单验证 | [35368994105](https://github.com/youq616/qbrain/actions/runs/35368994105) |

四条固定 push 运行通过；N44 两个发布任务按原条件跳过。最终审核归档不是
构建提交，不能替代上述身份，也不预先宣称合并后新触发的 CI 已完成。

| 验证 | 实际结果 |
| --- | --- |
| Windows/Linux 搜索专项 | 各 361 项解析检查、226 项进程检查、302 次命令通过 |
| 原有完整 Windows 套件 | N47N/N42/N44 各完整核对 60 个注册组，含已修复的 N31；PG 为 SKIP-PG |
| N42/N44 工件核验 | 7 工件、1,005 个源码文件、73 个包成员，1,216 项检查通过 |
| 专项报告核验 | Windows/Linux 各 1,746 项，各拒绝 8 种篡改报告 |
| 清单预检 | Windows/Ubuntu 各 19 组；本地普通及优化 Python 各 19 组通过 |
| 本轮额外清单对照 | 356 种合成输入，未发现 Python 通过而原生读取漏项的情况 |
| 搜索兼容与反向验证 | 248/248，含 22 组字节对比；旧版有 206 项重叠用例失败，符合预期 |
| 生成式与故障注入 | GCC、Clang ASan/UBSan 各 18,768 项通过；4 种故意破坏均被检出 |
| 原回归 | N47M 67/67、记忆/上下文/事实/召回/MCP/配置、4 个 CTest 组及 193/10/32 项验证器测试通过 |

额外本地检查在 Linux 执行，不能冒充 Windows 内存检查或真实客户端验收。
356 种对照中有 108 种重复行被 Python 更严格地拒绝，这是预期行为。
生成排列和失败用例不是等量独立功能或漏洞。

**结论：本阶段限定范围 PASS，未发现未解决的阻断项。** 审核由协调者本人
在开发之后另行进行，属于用户授权的分离工程自审，不是独立子代理或第三方认证，
也不保证绝对无缺陷。[完整审核](docs/nodes/N47N-HARD-AUDIT.md) ·
[精确证据](docs/nodes/n47n-evidence/FINAL-SUMMARY.json)。

## 交付与后续边界

c26 的 N44 inner ZIP 为 2,117,939 字节，SHA-256
`ec681a4599bf1b2a90f3848f5bf65b6d6a32e37254f32392d0709c43080b356c`；包内 EXE
SHA-256 `c35fadde8c8356b7243bf0b34cfd5c836bda27bb46da87eddcc79c1031bf05b5`。
它仍是测试工件，不是新公开发行。N47N 专项使用另一次编译，EXE 字节不同。

下一交付待办是将已审核修复整合到新的 Windows 预览和安装入口，本阶段没有启动
发布。其他 CLI 入口、真实 PG、完整 ACL/DLP、通用语义推断、衰减/画像、模型质量
费用、客户端消费/外发和正式签名仍有未完成项。本阶段通过不等于整个项目完成。
当前不需要用户本机操作或本地 Agent。

[N47M 原状态](CURRENT-STATUS-N47M.md)、[N47L 发布状态](CURRENT-STATUS-N47L.md)
和 [N47N 旧收尾状态](docs/nodes/n47n-evidence/PRE-CLOSURE-CURRENT-STATUS.md)保留为历史记录。
