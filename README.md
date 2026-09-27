# Qbrain

Windows 原生 C++20 / PowerShell 记忆与知识库，默认 SQLite + FTS5。
不要求 Docker、WSL 或 Python 常驻服务；可选离线评测使用 Python。

## N48N：原生 SQLite 深度体检与全文索引诊断

新增 `qbrain database check --database PATH [--timeout-ms N]`，检查明确指定的
数据库，不打开默认脑库、不读取模型配置、不修复原库。先取得只读已提交事务的
私有内存快照，再分别检查 SQLite 结构、外键、已知 v13 清单、页面关联、FTS 声明、
三个维护触发器及全文索引内容一致性。

普通 SQLite 完整性通过，并不证明全文检索索引与正文一致；新模块能识别这一类
失配。所有七项通过才返回0；发现问题返回1；输入/超时/操作失败返回2。
数据库上限256MiB、全部 source。只读连接仍可能创建空 WAL/SHM 或做共享内存记账，
不是文件系统无操作。它不是全业务语义验收、自动修复、来源认证或恶意数据库沙箱。

固定源码 `b6d0e800` 已通过 Windows/Linux 原生验收、原始数据回读和本人分离自审。
[完整用法](docs/integration/SQLITE-CHECK.zh-CN.md) ·
[当前状态](CURRENT-STATUS.md) · [结果审核](docs/nodes/N48N-HARD-AUDIT.md) ·
[实际合并记录 PR55](https://github.com/youq616/qbrain/pull/55)。

## 已有能力保持

N48M [备份/校验/仅恢复到新目录](docs/integration/SQLITE-BACKUP.zh-CN.md)仍保留，
不覆盖活动脑库。N48L 配对质量与主请求费用、N48J 执行回执计费、N48I 配对账本、
N48F/G/H 精确计价及响应导入，以及 OpenCode/MCP/回执生命周期能力不改。
原产品变化仅新增体检头文件和 main.cpp 早期入口；旧实现与旧测试没有被改写。

## Windows 交付与未完成边界

新 N48N 未签名原生工具包单独交付，含两个合成诊断样本，不自动安装、采集或修复。
旧 N48K/N48M ZIP、公开 N47X Release 和安装器保持不变，不用旧包验证新命令。
版本以受测源码和 EXE SHA256 为准，不以通用内部版本字符串为准。

真实客户端后续记忆消费、真实模型质量/全流程费用、PG 对等、签名、稳定版及
Issue40仍需独立验收。
[完成路线](docs/COMPLETION-ROADMAP.md) · [上一 README](README-N48M.md) · [LICENSE](LICENSE)。
