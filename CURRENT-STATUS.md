# Qbrain 当前交付状态

## N47E：仓库实现、阶段审核、合并与固定预览发布已完成

[PR #20](https://github.com/youq616/qbrain/pull/20)已合并，产品合并提交
`3499f19b8191fbbe38d9c05a133901395821192b`。
实际产品、原生测试和单独工程复核源码为
`c6c76a2f3fd2dd0b07326ef6e19c1a59283402e8`，树
`07f00ef07fc1cb79642472b63052221c84bb2db1`。
审核头e1857c4只增加/更新五个文档，合并与审核头没有文件差异。
后续发布说明不改变已测试EXE、安装器或测试包字节。

[公开仓库 Release：promotion-preview-c6c76a2f](https://github.com/youq616/qbrain/releases/tag/promotion-preview-c6c76a2f)
选择 `qbrain-windows-x64-promotion.zip`，1986872字节，SHA256：
`50395502dbcf65d142fd36a0f511dc8b764971bcfd5854d466e8d2e38e04ae73`。
EXE3965952字节，SHA256：
`f9ed4d157f46e5ee25fc1f92449a805b1c9a51bdf65faf9a42b443c9266e2c29`。
完整解压，阅读LOCAL-FACT-PROMOTION.zh-CN.md及HOOK-FACT-RECALL.zh-CN.md。
未签名开发预览，原CI字节，不重打包；不需要本机编译器，不能用旧dist/旧哈希包替代。

## 本阶段实际连接

安装器新增独立默认关闭的 `-EnableFactPromotion`，要求显式 `-EnableCapture`。
它不自动打开 `-EnableFactRecall`、外部模型许可或MCP写权限。启用后，当前用户事件
成功本地提取的完整原话会自动整理为证据事实，不再需要另行逐条调用fact create。
同时提供FactStore::promote_event、fact promote --event及既有MCP fact_promote动作。

predicate固定为memory.<category>，confidence=null，保留否定与完整原话。不做通用
语义推断、真假判断或自动矛盾关系。相同独立原话追加支持，重放不增版本；物理支持
16条上限明确跳过，任何同源退休同句事实阻止自动复活。事实/证据批次原子，备份与
可选表初始化是独立准备步骤，失败后可能保留。关闭开关不撤销已整理的事实。

旧候选的过期支持续接缺口已经修复：仍active的事实仅在全部旧支持完整且已过期时，
允许新增当前有效同句证据。旧expiry/status不重置，过期支持不重新进入live读取；
部分损坏、删除页、退休及16条物理上限不会被绕过。旧aa34候选未作本次交付。

N47D事实Hook及统一JSON预算保留。采集、整理、召回是分别授权的行为；提供给授权
客户端的上下文可能由客户端发送给模型，没有额外Qbrain模型请求不等于没有客户端
外发。逐事件forget不安全擦除备份、WAL、既有客户端上下文或其他独立同句记忆。

## 已核实的原生与单独工程审核

开发34906704753、N42 34906704707必需任务通过：Windows53个准确注册组；promotion
单元在Server2025/Server2022/portable各18场景237断言；Windows/portable实际EXE
CLI/MCP/Hook事件夹具68项77命令（70个预期exit0、7个预期exit1）；PS5.1/7新安装检查
各33项。全部原事实/冲突/召回/Hook/HTTP/队列/CJK/记忆和双PowerShell门槛保留通过。
真实PG DSN依旧明确SKIP-PG，不计作PG对等验收。

单独工程自审重新用Clang17 ASan/UBSan构建SQLite C及C++，18/237和68/77实际运行
通过；独立预期状态oracle47个事件、218次命令、1003条重复状态断言通过；两个故意
破坏的隔离副本准确失败于退休保护和完整历史证据检查。96项报告门槛、216项固定
原始源码/报告/包回读通过，760文件源树一致。没有未解决本阶段P0/P1，不是绝对无
缺陷保证、第三方或真实子代理审核；Linux补查不是Windows sanitizer或真实宿主。

发布34921352237成功：校验已合并PR/固定审核与产品树、原CI及Artifact摘要，完整
复验unit/process/install报告后上传新草稿，下载逐字节比较三项资产再公开。
未重编译/重打包/覆盖旧Release，未开启通用未审核自动发布。

[阶段复核](docs/nodes/N47E-HARD-AUDIT.md) · [测试摘要](docs/nodes/n47e-evidence/SUMMARY.json) ·
[发布记录](docs/nodes/n47e-evidence/RELEASE.json)

## 唯一需要本机补验的边界

**真实已登录客户端消费尚未认证。** 按[固定本机任务](docs/integration/N47E-LOCAL-ACCEPTANCE.zh-CN.md)
执行最多三次新的隔离Claude会话：A1真实自动采集/提取/整理，A2独立新会话自动召回，
B1另一脑库隔离，再关闭/卸载。不能手工写入事实或重放Hook来替代第一段自动路径。
任务固定于e1857c495b0d605cda69668bd1c1bb5579b74038，SHA256：
`90e80b34fcbfdf3591baa14503845954bd8f25a3171c93aa5efac54d0e627f5b`。
不安装编译器、不改源码、不配置GitHub写凭据、不重复审核，不修改Codex401认证。
只交一个脱敏ZIP。真实事件/模型消费和合成夹具分开记录，不翻改trace来虚报通过。

后续通用语义提取、冲突推断、衰减画像、PG对等、模型质量费用、完整ACL/DLP、真实
Codex闭环及正式签名仍需开发或验收。N47E仓库阶段完成不等于整个项目完成。
