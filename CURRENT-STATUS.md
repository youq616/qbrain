# Qbrain 当前交付状态

## 已合并并发布：N47G 批量预检与原子化归档／恢复

[PR #23](https://github.com/youq616/qbrain/pull/23) 已合并，合并提交
`9a7ecbbf61fc2c086a657527cfb27521d9dc84fe`。实际产品／原生测试源码为
`b1292b54543b9f54cd5e2b71f4ae4bf5f6247385`，源树
`572dce7081140b7869821e9e2f98b7f1429d6328`。
审核头只增加 docs 下7个说明和补充探针证据文件，没有改变生产代码、原测试、构建
或包字节；合并提交与审核头无文件差异。后续交付说明不代表重新编译。

[预览 Release：batch-preview-b1292b54](https://github.com/youq616/qbrain/releases/tag/batch-preview-b1292b54)
已公开。产品 `qbrain-windows-x64-batch.zip`，2,025,933 字节，SHA256：
`85e0f15f907c2bf4ac39c6356d231637251209a902eb7fe6a50476161ae10603`。
完整解压，阅读 `BATCH-LIFECYCLE.zh-CN.md`。仍是原CI字节的未签名开发预览版，
没有重打包，不是整个融合项目的最终发行。运行包不需要本机编译器。

## 本阶段实际能力

`fact batch-preview` 只读预检；`fact batch-apply` 显式批量执行归档或恢复。
既有MCP使用 `memory_read(view=lifecycle_batch,payload=...)` 和
`memory_write(action=fact_lifecycle_batch,payload=...)`，没有新增工具名。
一次选择1..32个同来源唯一事实，每项提供当前expected_revision。重复ID、重复JSON
键、错误类型及无关字段拒绝，输入8KiB，完整结果metadata32KiB，不复制原话。

预检不写库、不建表、不备份、不取得写锁，也不是预约或版本锁定。PREVIEW中的
after值只是预测。实际执行在一个写事务内重新核对全部证据、状态和版本；任一
失效、版本变化、SQL或提交失败，整个策略/revision批次回滚，不允许前半批成功。
无变化项仍需要有效证据和当前版本，但不重复增加revision。

首次准备仍沿用N47F：先备份磁盘库和初始化可选表，策略应用是另一个事务。后续
执行失败可能留下备份/空表，但不会部分提交策略。条目数不限制备份I/O或硬实时。
归档不是遗忘或保密边界，必须保留有效直接反证；恢复不能复活退休、过期、遗忘
或损坏事实。旧单条接口和安装默认开关保持，旧二进制仍不认识归档策略。

## 已执行验证与单独审核

开发35093371931及N4235093372100必需任务全部通过：Windows准确55注册组；批量单元
在两Windows版本、portable和ASan+UBSan各15场景/259断言；批量实际CLI/MCP40检查/
54次预期退出（39次exit0、15次负向exit1）。全部旧事实、生命周期、自动整理、Hook、
召回、冲突、HTTP、队列、CJK、记忆和双PowerShell门槛保留，真实PG DSN仍SKIP-PG。

阶段单独工程自审又在Linux用GCC14.2重新构建和执行batch15/259、process40/54、
旧lifecycle17/180、14报告门槛和17注册门槛。补充5场景67断言实际测试提交被拒绝、
后续ABORT/FAIL/ROLLBACK和真实读锁阻塞COMMIT；整批策略/版本/原话/更新时间不变，
autocommit与原busy_timeout恢复。补充源码和原结果存入n47g-evidence。

6个原始Artifact的234项回读重建796文件精确源码树，并验证完整报告和产品字节。
探针二进制未另下载，身份依赖固定原报告及原打包过程的实际探针校验，审核中明确。
本轮未发现未解决P0/P1，不保证没有所有潜在缺陷；是所有者授权的工程自审，不冒称
第三方或真实独立子代理。没有新增已登录客户端实机验收。

发布35101495343成功：绑定已合并PR、固定源码／审核、原始任务与摘要，重验报告，
创建新草稿后下载逐字节比对三项资产再公开。不重编译／重打包、不覆盖旧Release，
不启用通用未审核自动发布。

[阶段审核](docs/nodes/N47G-HARD-AUDIT.md) · [测试摘要](docs/nodes/n47g-evidence/SUMMARY.json) ·
[发布记录](docs/nodes/n47g-evidence/RELEASE.json)

## 既有能力与未完成边界

N47F单条归档／恢复及只读年龄检查保持；年龄来自有效支持created_at，不是使用
频率、确认时间或可信度，陈旧只是提醒。N47E明确开启的本地规则事实整理和N47D
Hook事实召回保持，N47A-C证据绑定、显式冲突和含反证召回保持。

N47D原实机证据已按PR21归档；所有者转交N47E真实Claude自动链路24PASS、1直接trace
未保留、1Codex认证BLOCKED的摘要单独记录，不冒称本轮读取了原始N47E ZIP，也不
将其计为N47G新宿主验收。无需用户重复同一任务或修改host_consumption标记。

尚未实现通用语义合并／冲突推断、使用／确认计数、自动衰减归档、画像、推断时间
替代、百万事件性能保证；PG对等、完整ACL/DLP、模型质量费用和正式签名也未完成。
本阶段是显式批量管理，不是整个生命周期方案或整个项目完成。

当前没有必须交给本地Agent的新任务。不需导出源码、编译器或GitHub写权限；Codex
网关认证不在本轮修改。真正需要本机工作时仍只给一个完整提示词，文件先放仓库，
明确固定来源、哈希和用法，不让本机并行重写相同代码。
