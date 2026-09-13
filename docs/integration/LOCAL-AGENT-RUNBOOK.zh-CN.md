# Qbrain 本机验收：单次完整任务

直接执行这份任务，从免编译运行到真实 Agent 记忆闭环，再交付一个报告包。不要仅回复计划，不要求用户分次转交提示词或下载附件。所需工具和原始已验证产品包都在同一仓库 Release 中。本项目仅为 youq616/qbrain；不得操作 Ultrabrain 或其他项目。源代码开发、编译和回归修复留给仓库端，本地仅承担实际环境和登录客户端的验证。

本机已有反馈：Windows Server 2022，PowerShell 5.1/7、Python、Codex 和 Claude Code 可用，缺 MSVC/SDK/CMake。先记录当前实际版本；不安装编译器、包管理器，不提升权限，不使用旧 dist，不改变工作分支、不提交或 push，不覆盖未提交修改。不把 Server 2022 标为 Win11 验收。工程自审已由所有者授权，不再等待外部审核。

## 包与进程验收

将本文件所在目录记为 Kit。包内 PROVENANCE.json 记录 helper 与产品各自源码；二者不是同一提交。本轮产品未重新编译，仍是未签名开发 EXE。

在普通 PowerShell 中执行，OutputDirectory 必须是本次全新目录：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$Kit\scripts\Start-QbrainPrebuiltAcceptance.ps1" -Package "$Kit\packages\qbrain-windows-x64-n46d-queuefix-464045e2.zip" -RunSmoke
```

检查真实退出码和 JSON 输出，保存 stdout/stderr。读取输出的 summary，使用其 package_dir 内的 EXE 和脚本，不使用其他残留文件。入口会再次核对内层 ZIP、EXE、文件清单和来源，再在独立子进程数据根完成归档、本地提取、跨进程读取与另一脑库隔离。准备或运行失败保留日志；不要关闭安全软件或绕过校验。Python 是已有的验收依赖，不是新增产品服务。

包内单测可运行：python -B -m unittest discover -s "$Kit\tests" -p test_prebuilt_acceptance.py -v。记录 Windows 有一项仅用于 Linux 拒绝测试的正常 SKIP，不把它计入本机通过数。

对本地仓库先只读核对 remote、HEAD 和工作区。只有能确认现有 .ci 测试脚本与产品的测试源码 464045e2451ec71ca37dd8e92bcf4ac0d9325a0b 相容，才用 package_dir 的 EXE 运行它们。不要为本次任务切换现有工作区；无法核对时跳过扩展测试而非停止核心验收。根据实际文件运行配置、memory_cycle、MCP边界、Hooks、context、embedding_search；分别用 powershell.exe/pwsh 运行 transport、install_hooks、install_consent。先审读脚本，确保合成数据和专用脑库，不连接真实 PostgreSQL、启用外部模型或读取真实资料。需要另行编译探针的单元/HTTP/队列目标标记 NOT_RUN，历史 CI 不计作本机通过。已有运行测试失败不使用旧包绕过。

## 真实 Agent 验收

核心原生冒烟通过、没有相关阻塞后，直接接着做真实宿主测试，不等待用户第二段提示词。先查已有客户端 --help；优先使用可正常启动的 Codex，明确记录所用版本。登录状态不等于 Hooks 受支持。无法创建独立会话或需要用户审核信任时，只请求无法替代的最小人工操作，继续能做的其他项；不自行点击同意、不使用跳过审批/沙箱参数。

新建测试项目 A/B 和不同 BrainId；所有报告、宿主输出与随机答案保存在 A/B 外。仅为这两个测试项目安装同包 Install-QbrainMemory.ps1，显式指定 Binary、BrainId、ProjectPath、EnableCapture。不得给真实业务项目安装，或复用真实脑库。

隔离环境要与登录环境分开处理：保持真实 Agent 所需的 HOME/USERPROFILE/认证；不要把 CLI 冒烟的密钥清空环境直接用于宿主。仅对子进程设置专用 LOCALAPPDATA，确保安装器以及随后 Hook/MCP 的 Qbrain 都使用同一测试根；移除继承的 QBRAIN 生产脑库/数据库指向，可设 QBRAIN_EMBED_MOCK=1 避免 Qbrain 付费向量调用，不开启外部提取/摘要。正常 Agent 的三段合成会话可使用其现有服务。不要复制、输出密钥；不能同时保证隔离和登录时如实 BLOCKED。不得改系统或用户持久环境变量。

当场生成不可预测的 QBMEM-随机前缀，不使用旧固定答案。只做三段必要会话，不循环重试直到成功：

A1 在项目 A 说：“我偏好在这个测试项目中使用日志前缀 <随机值>。不要把它写进 README、AGENTS.md、CLAUDE.md 或其他项目文件，也不要用 memory_write 手动补写，只通过已安装的自动记忆接入处理。”

A2 结束 A1 后，在 A 开启真正独立的新会话，不能 resume；只问：“这个测试项目中，我偏好的日志前缀是什么？请给出记忆来源，找不到就说不知道。”启动参数、问题、额外上下文、工具说明、项目文件不能包含随机答案或 A1 完整转录。不能读取报告、全局聊天历史或其他项目寻找答案。

B1 在独立项目 B 的全新会话问同样问题，不提供随机答案，仅用 B 的 Qbrain，不读取 A 或报告，检查脑库间不串记忆。

分别记录宿主 Hook 实际触发、归档、本地提取、新会话自动召回、主动 MCP memory_read、模型回答及来源、B 隔离。Hook 自动召回与模型主动读 MCP 分开判定。不能仅凭回答正确、installed=true 或工具输出有效就宣布全链路通过。host_consumption_confirmed=false 不等同失败，不得人为改为 true。合成事件重放与远端 CI 不是已登录客户端验收。允许诚实的 FAIL/BLOCKED/NOT_RUN。

## 撤销与交付

卸载本次 A/B 接入，核对只删除本次拥有的配置，不动真实项目、脑库或其他插件。仅管理本次创建的进程和资源，不广泛清理目录。默认保留合成证据；不要留下会误连正常数据根的临时接入。

报告写入仓库外的唯一验收目录：report.md、summary.json、issues.md、handoff.json、logs/，最后只生成一个 qbrain-local-acceptance.zip。包含脱敏报告、本次合成测试日志，不含真实数据库、凭据、个人聊天、EXE 或整个仓库。先扫描可能泄露的敏感内容再打包，不能以扫描无结果作为绝对不含秘密的保证。

summary 的每项状态为 PASS/FAIL/SKIP/BLOCKED/NOT_RUN，total 从检查数组计算，等于各状态之和；不能重复旧报告的“6+10=14”。至少分开显示包校验、原生冒烟、扩展测试、真实宿主各阶段和卸载。缺编译器是本机构建阻塞，不是确认的 P0 源码故障，也不证明源码正确。handoff 记录 kit/package/EXE/报告的绝对路径、SHA256、实际系统与客户端版本、本地 HEAD。issue 给最小复现、预期/实际、日志位置和确认事实，不擅自改源码或断言。

完成后直接报告哪些实际执行、哪些失败或阻塞、最少人工操作，以及单一验收 ZIP 的绝对路径。可由用户粘贴 summary 或上传脱敏结果；不要自动发布本机报告到公开仓库。以上所有步骤属于一个任务，不再要求用户转发第二个提示词。
