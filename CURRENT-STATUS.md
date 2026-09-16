# Qbrain 当前交付状态

## 已合并并发布：N47F 可撤销归档与生命周期检查

[PR #22](https://github.com/youq616/qbrain/pull/22) 已合并，合并提交
`3f9bc3671f30b8547a1c8ab1371352d9427974ef`。
实际产品/原生测试源码为 `cafb48667177002ae6ea0f1976eea2f388826024`，
树 `f0111dbec7b3158dc495b3a6394332c23f557212`。
审核后只有文档变更；合并提交与审核头无文件差异。后续发布记录不代表再次编译。

[预览 Release：lifecycle-preview-cafb4866](https://github.com/youq616/qbrain/releases/tag/lifecycle-preview-cafb4866)
已公开。下载 `qbrain-windows-x64-lifecycle.zip`，2,005,834 字节，SHA256：
`c16f15a7ad318beb58059b05d3f400399b33d34c000d040c3c1ddcc179641f55`。
完整解压并阅读 `FACT-LIFECYCLE.zh-CN.md`。原 CI 字节、未重打包、未签名开发预览，
不是整个融合项目完成。运行包无需本机编译器，不用旧 dist 或旧哈希入口替代。

## 本阶段实际实现

`fact archive`、`fact restore` 及相应 memory_write 动作要求当前 expected_revision
和有效完整原话证据。归档不改变事实退休状态，不改原话或证据；它只限制该事实
作为默认 fact recall/已开启事实 Hook 的命中入口。其他事实的有效直接冲突证据
必须保留，显式 read/conflicts 也可读，因此归档不是遗忘或保密边界。

restore 不能复活 retracted、superseded、expired、forgotten 或损坏事实。同一事实
重新获得自动整理支持不会清除归档。最后证据被删除后，归档元数据随事实级联清理。
首次磁盘模块初始化先备份；表准备和状态变更是两个事务，失败可能留空表/备份，
但不会留下半个归档或错误 revision。旧二进制不认识归档策略，降级可能重新召回。

`fact lifecycle` / `memory_read(view=lifecycle)` 只读检查年龄。年龄来自有效支持的
最新 created_at，不是最后使用时间、用户确认次数或可信度。stale 是提醒，不是
新的事实状态；异常存储时间为 unknown/null，未来时间为 clock_anomaly。
读路径不写计数、不建表，保留来源、完整反证、快照和输出预算。

## 原生验证与单独工程审核

35076641849、35076641751 的必需任务已通过：Windows 54 个准确注册组；生命周期
单元在两套 Windows 及 portable 各17场景/180断言；Windows/portable 进程36检查/
58次预期退出（52次exit0、6次负向exit1）。旧事实、冲突、召回、Hook、自动整理、
队列、CJK、HTTP、记忆及双PowerShell门槛全部保留，真实PG DSN仍SKIP-PG。

早期读路径事务授权回归和时间强制转换缺陷均已修复，原失败记录保留。新源码
ASan+UBSan在独立Linux CI 35077139073实际执行通过；以前本地ASan因地址限制在
main前失败的记录不改写。补充复核重新GCC14.2编译并执行17/180、旧recall15/330、
36/58实际进程与111报告门槛，全部通过。6个原始Artifact的212项回读核对了782文件
源码树、报告及产品字节；探针EXE未另下载，边界在审核中说明。

未发现本阶段未解决P0/P1，不保证绝无潜在缺陷。审核由协调代理按所有者要求单独
进行，是工程自审，不冒称第三方或真实独立子代理。

发布35087032393成功：重新绑定已合并PR、固定源码/审核、原始任务和摘要，完整
复验报告后上传新草稿、下载逐字节核对三项资产再公开。不重编译/重打包、不覆盖
旧Release、不启用通用未审核自动发布。

[阶段审核](docs/nodes/N47F-HARD-AUDIT.md) · [测试摘要](docs/nodes/n47f-evidence/SUMMARY.json) ·
[发布记录](docs/nodes/n47f-evidence/RELEASE.json)

## 客户端证据与后续边界

N47D原实机证据已按PR21归档。所有者后来转交的N47E本地Agent摘要报告Claude自动
输入→采集→提取→事实整理→新会话召回通过；26项中24PASS、1直接trace未保留、
1既有Codex认证BLOCKED。这里记录为用户转交摘要，不冒称本轮读取了原始N47E ZIP，
也不继承为新N47F宿主验收。不要让用户重复已经执行的同一任务或修改消费标记。

当前没有必须由本地Agent执行的新任务，不需重新导出、编译器或GitHub写凭据。
既有Codex网关认证由用户单独掌握，不用Claude结果替代Codex验收。

尚未实现：通用语义合并/冲突推断、使用/确认计数、自动衰减归档、画像、推断时间
替代与百万事件性能保证。真实PG对等、完整ACL/DLP、模型质量费用及正式签名发行
也未完成。N47F本切片完成不等于前面对话列出的全部生命周期设想均已实现。
有真正本机任务时仍只给一个完整提示词，文件先放仓库并提供固定来源、校验和用法。
