# Qbrain

**Windows 原生个人知识与 Agent 记忆项目**。保持 C++20 / MSVC 与 PowerShell 路线，不把 WSL、Docker 或 Python 服务作为产品运行前提。默认使用 SQLite + FTS5；可选 PostgreSQL 后端需单独构建和验证。

本仓库由项目所有者选定为后续开发位置。原始代码来自 MIT 许可的 `Lordakee/qbrain`，固定基线为 `2e5c4f0bf310ca4f340b3a2295d2dfd79d3b8325`，灵感来自 gbrain。

## 当前状态：N42 基础修复开发版

- [PR #1：N42 源码修改与验证](https://github.com/youq616/qbrain/pull/1)
- [Issue #2：后续完整优化路线](https://github.com/youq616/qbrain/issues/2)
- [原生 Windows / 局部可移植测试](https://github.com/youq616/qbrain/actions)
- [开发状态与限制](docs/integration/DEVELOPMENT-STATUS.md)

`main` 在合并前保留导入基线，修复位于 `optimization/n42-foundation`。请核对所看的分支和 CI 的实际提交号。

本批已经修改：检索结果保留来源身份、按正确来源读取综合回答的证据、UTF-8 安全显示、受影响读取接口的来源检查、去除图片查询的隐式上传、禁止只读 MCP 综合回答隐式保存、重排结果校验，以及原生 Windows CRLF 宏续行识别。新增测试连接到原有构建与回归入口。

**本批没有完成：**会话正文语义提取、各 Agent 自动读写 Hooks、L0/L1 语义摘要、完整 gbrain 协议、全项目 ACL 审计和总成本基准。不要把接口数量等同于功能等价，也不要将本批描述为“全盘优化完成”。

## 构建和测试

在装有 MSVC Build Tools 的 Windows 测试环境中，从仓库根目录运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-cl.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-tests-cl.ps1 -SkipProductionBuild
```

第二条仅在第一条已成功且源码未改变时复用同一轮生产对象；不确定时不传 `-SkipProductionBuild`。测试应放在隔离的开发环境，不要让真实凭据或生产数据库环境变量进入测试。

CI 另用 Python 编排真实可执行文件的 MCP 测试；Python 仅为测试工具，不是 C++ 产品运行依赖。没有 PostgreSQL 测试 DSN 时，相关集成组明确跳过，不计作真实 PostgreSQL 验证。

## MCP 与数据

默认只读，需要 Agent 写入时显式选择 `--allow-write`：

```powershell
claude mcp add qbrain -- "D:\Projects\Qbrain\build\cl\qbrain.exe" serve
```

路径须换成本机实际构建路径。仅连接 MCP 不代表自动采集与召回 Hooks 已安装。

数据默认位于 `%LOCALAPPDATA%\Qbrain\`。不要将数据库、API Key、Token、完整会话或真实个人资料提交到仓库。

## 重要：旧产物不是修复版

仓库 `dist/` 内已有的文件是上游历史产物，**不是从 N42 修复源码重新构建的安装包**。CI 成功也不等于所有 Windows 11 Agent 场景已验收。不要据此覆盖正在使用的程序或迁移生产记忆库。

## 许可

MIT，保留原始版权和许可声明。借鉴其他系统的设计不代表直接复制其源码或取得额外许可证。
