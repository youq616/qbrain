# 本机验收：编译不是运行已有开发包的前提

## 分工与模式

缺少 MSVC/Windows SDK 是本地源码构建的环境阻塞，不等于源码无缺陷，也不阻塞
远端开发。`build-cl.ps1` 直接使用 cl/link；CMake 是另外一些构建/测试路径的依赖。
仓库与 Windows CI 负责源码构建、C++ 回归和专项探针。本地优先用已验证开发包完成
系统兼容性、两版 PowerShell 及已登录 Agent 的实际事件与跨会话测试。
没有 winget 的机器不要从 winget 命令开始；本模式无需安装编译器或包管理器。

## 不编译，先校验并冒烟

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Start-QbrainPrebuiltAcceptance.ps1 -Package "C:\Downloads\qbrain-windows-x64-n46d-queuefix-464045e2.zip" -RunSmoke
```

本验收工具需要现有 Python 3.10+，不是新增的 Qbrain 产品运行依赖。只接受
N46D 队列修复内层 ZIP，源码 `464045e2451ec71ca37dd8e92bcf4ac0d9325a0b`，
ZIP SHA256 `4f43e91853602bd141822ad11650ddab9643a3471f8a86bd2c615ffb61c460ee`。
旧 `dist/`、早期 N46D 包、外层 Artifact ZIP 或被重新打包的 ZIP 均不替代它。

脚本先校验外部固定 SHA256、ZIP 路径/文件类型/大小、完整清单、每个文件哈希、
EXE 摘要及来源报告，再写入新目录。不会覆盖现有目录，不自动下载、安装软件、
提升权限、改持久环境变量、改正式项目或启动 Agent。它没有“跳过哈希”选项。
脚本只能防止输入错误及已列出的路径问题，不能隔离具有相同本机权限的恶意进程。

默认只解包；`-RunSmoke` 在原生 Windows 中执行手动归档、保守规则提取、独立进程
读取和另一脑库隔离检查。HOME/USERPROFILE/LOCALAPPDATA/APPDATA/TEMP/TMP 仅对子进程
重定向，Qbrain/模型密钥变量移除。不触及真实脑库或外部模型服务。日志与合成脑库
保留在唯一验收目录中。失败不自动重试，也不删除诊断资料。

输出 JSON 包含 `summary` 和 `package_dir`。摘要计数从检查列表生成，PASS/FAIL/
BLOCKED/SKIP/NOT_RUN 的总和必须等于 total。准备成功不等于整体验收成功；历史CI
结果不会被计作本机已运行。Linux 请求 Windows 冒烟会明确 BLOCKED。

## 下一阶段：已有进程测试和真实宿主

以摘要输出的 `package_dir\qbrain.exe` 执行现有 `.ci` 进程测试，无需编译其余探针。
先核对所选测试脚本与二进制版本对应，再分别运行记忆、MCP、Hook、上下文、配置、
Embedding 搜索隔离及已安装 PowerShell 版本的安装/撤销测试。缺少测试专用 EXE 的
C++ 单元、队列和原生HTTP探针只记录远端证据；不称其在本机重新通过。

真实 Agent 测试另行执行，不能用上述脚本的假提供方或事件重放替代。只在新建项目A
和独立脑库中安装，第一段会话输入随机测试偏好；第二个独立会话的问题不得包含答案，
不能 resume 旧会话；项目B使用另一脑库检查不串记忆。区分 Hook 实际触发、归档、
召回输出、MCP 主动读取和模型消费几个阶段。正常审核客户端信任，不绕过权限。
真实客户端需要原有登录环境；不要套用 CLI 冒烟的 HOME/密钥清空环境令其退出登录。
安装器、Qbrain Hook/MCP 子进程必须使用一致的测试数据根；无法隔离则记录具体阻塞。

报告按实际操作系统命名。Windows Server 2022 结果不是 Win11 用户桌面验收；
CLI 已登录也不是 Hook/跨会话能力已验收。最终只上传脱敏报告、合成测试日志，
不上传真实数据库、模型密钥、用户目录或个人聊天。

## 验证入口

`python -m unittest discover -s tests -p test_prebuilt_acceptance.py -v`

专用工作流 `prebuilt-acceptance.yml` 测试 Python 工具、PowerShell 5.1/7 包装入口及
同一固定 EXE 的原生冒烟。它不重新编译产品、不替代原有完整回归。原始 GitHub
Artifact 将于2026-09-26过期；过期时CI必须报错，维护者需改为已验证的新固定来源，
不得静默回退到旧 dist/latest。用户手上原始 ZIP 离线校验不依赖 Artifact 下载。
