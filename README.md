# Qbrain

Windows 原生 C++20 / PowerShell 记忆与知识库，默认 SQLite + FTS5。
不要求 Docker、WSL 或 Python 常驻服务；可选离线评测使用 Python。

## N48L：逐题质量与主请求费用联合评估

`tools/acceptance/model_evaluation.py export|verify` 将同一次模型执行的原始回答、
离线评分答案与费用账本绑定起来。分别报告 50 题的依据上下文正确率、25 道可解题
的解决率，并逐题列改善/退步。更便宜的拒答或总分抵消不能代替解决问题。
完整响应且费用可比时才给本批样本的逐题优劣/取舍关系，不认证真实模型效果。

原模块 d79181be 与本轮独立审核 7e5d4ddc 均取得 Windows/Linux 结果；旧实现、
评分器和计价保持原字节。最终结论见 [当前状态](CURRENT-STATUS.md)、
[中文用法](docs/integration/MODEL-QUALITY-COST.zh-CN.md)、
[分离自审](docs/nodes/N48L-HARD-AUDIT.md) 与
[PR53](https://github.com/youq616/qbrain/pull/53)。

## Windows 候选包与使用边界

已交付的 N48K Windows 集成候选仍可使用，且其 ZIP 没有被本轮改写。
它含 N48I 原生费用对照与 N48J 费用桥接，但不会自动包含新的 N48L Python 脚本。
新工具从本轮源码或单独工具包取得；不覆盖旧包、脑库或历史报告。
[候选包说明](docs/integration/WINDOWS-CANDIDATE-N48K.zh-CN.md)。

N48L 离线运行，不发起付费请求、不安装 Hook、不修改脑库，也不传出评分答案。
只计计划内主请求，不含全部辅助费用；结构化测试不等于通用回答质量或登录客户端
实际记忆消费。未签名候选、PG、签名、稳定版和 Issue40 仍有独立验收要求。
[此前路线](docs/COMPLETION-ROADMAP.md) · [上一 README](README-N48K.md) · [LICENSE](LICENSE)。
