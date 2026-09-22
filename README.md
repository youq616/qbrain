# Qbrain

Windows原生C++20 / PowerShell记忆与知识库，默认SQLite + FTS5。
应用不需要Docker、WSL或Python服务；可选评测与开发工具使用Python。

## 最新源码：N48G供应商用量导入与精确计价

新增cost import，把明确格式的OpenAI Chat／Responses或Anthropic Messages最终
非流式响应转换为互斥Token桶，直接返回规范化输入和原cost report精确结果。
不联网、读密钥、打开脑库或自动查价；未知用量不当0，同批重复响应和矛盾计数拒绝。
失败尝试若有用量也计价，输出不包含响应正文。金额完整不是账单真实性或全部费用。

两平台各59直接检查，每模式231检查／230调用；独立生成768种用量状态并用Fraction
核对全部费用，每模式824调用通过。原费用与应用回归保持，独立自审已归档。
[当前状态](CURRENT-STATUS.md) · [导入用法与合成示例](docs/integration/PROVIDER-USAGE-IMPORT.zh-CN.md) ·
[本人分离自审](docs/nodes/N48G-HARD-AUDIT.md)。

## 已有源码模块

N48F提供规范化Token费用报告；N48E集成OpenCode项目配置完整生命周期并取得固定
1.18.31宿主加载／连接证据；N48D检查隔离MCP启动／目录／退出，不代表真实模型消费。
N47Y统一回执完整性；N47Z提供32回执／8事实的只读批量预览、精确批准和整批回滚。
[费用定义](docs/integration/TOKEN-COST.zh-CN.md) ·
[OpenCode生命周期](docs/integration/OPENCODE-LIFECYCLE.zh-CN.md) ·
[隔离自检](docs/integration/ISOLATED-MCP-CHECK.zh-CN.md) ·
[批量回执](docs/integration/USAGE-BATCHES.zh-CN.md)。

## 当前公开下载仍为N47X工程预览

[windows-current-preview-b810d689](https://github.com/youq616/qbrain/releases/tag/windows-current-preview-b810d689)。
选择qbrain-windows-x64-n47x-preview.zip及同版START-HERE、SHA256SUMS和PROVENANCE。
ZIP为4,327,611字节，SHA256：
`c517582c1ea0e0795e881155edd4d34288e3a002dc3bc7657dafcb96a1eb8b4d`。
公开包不含之后N47Y/N47Z/N48D/N48E/N48F/N48G源码；本轮不替换旧资产或标签。
[该版本安装升级说明](docs/integration/CURRENT-PREVIEW-N47X.zh-CN.md)。仍为未签名开发预览。

## 其他边界与构建

真实后续会话记忆消费、模型质量／费用、PG新模块对等、语义确认／画像／衰减、
ACL/DLP、规模性能、签名和稳定版终验仍有未完成项；Issue40根因未确定。
[完成路线](docs/COMPLETION-ROADMAP.md)。价格卡由调用方核实，不把合成费率当报价。

原生构建使用scripts/build-cl.ps1和scripts/build-tests-cl.ps1；只有同轮生产构建成功
且源码未变才使用-SkipProductionBuild。导入模块直接测试使用tests/usage_import独立
CMake项目，旧60组不代表已运行全部新增目标。确需本机任务时遵循
[单提示词交接](LOCAL-AGENT-HANDOFF.md)。[上一README](README-N48F.md) · [LICENSE](LICENSE)。
