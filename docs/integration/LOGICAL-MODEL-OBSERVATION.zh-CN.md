# N48X 逻辑模型调用与 HTTP 关联（独立未合并候选）

此模块基于精确 0e3c 的 HTTP 观测接口；不改 PR65 冻结分支或旧报告格式。
新增 `observe-model` 只在显式调用时启用，默认无文件、无新增用量解析。
覆盖四个实际函数入口：chat_complete、embed_texts、embed_image、apply_reranker。
更高层在进入这些函数之前返回、其它 provider 回调、查询缓存命中和其它网络栈
不在本模块完整覆盖承诺内。

## 入口

`qbrain observe-model --output NEW_DIRECTORY -- EXISTING_COMMAND ...`

目录必须不存在。它转发原命令的 stdout/stderr，业务行为与授权保持原样；
额外目录不是全进程脱敏器，旧 rerank audit 也不由本模块改写。
可以先执行 `qbrain observe-model --output local-demo -- help`，此时两类调用计数都为0。

开始时写 started.json；calls/ 中每个实际逻辑入口有 start/finish，http/attempts/
沿用原 HTTP 事件；links/ 使用真实 HTTP 序号关联最内层逻辑调用；
最终 logical.json、http/report.json、report.json 是三份不同范围的记录。

复核：`qbrain observe-model verify --logical DIR/logical.json --http DIR/http/report.json`。
结构及关系不一致时拒绝；记录不完整时返回2。不能认证伪造的全部输入或签名，
不能因摘要相同就断言外部服务器收到请求。断电或终止缺少最终文件时不可当作完成。

## 怎么理解数据

一次 rerank 可能调用 chat：记录两个逻辑入口，但只有内层 chat 关联一个 HTTP attempt。
父子不是重试，向量请求重复执行也不自动去重；没有证据的 retry_relation 为 null。
每个逻辑记录的 tokens/price/cost 始终为 null；拒绝、mock、空输入不被写成外发或免费账单。
成本仍从原 `observe cost` 对 `http/report.json` 计算，适用费率与重试标签必须明确声明；
不要把逻辑记录与 HTTP 记录相加计价。

path 为实际分支：缺凭据、非法输入、empty/disabled、local_mock、local_baseline、
custom_callback、remote_candidate。remote_candidate 只表示代码进入准备外部调用的
分支，不证明发送；实际 HTTP 入口和 send_invoked 的边界由原记录说明。
api_result_ok 只是原返回结构的 ok，未认证任务/模型成功。rerank 返回向量没有 ok，
该字段为 null；fallback_taken 只记录代码确实取了回退分支。HTTP200、API ok 和
provider 状态三者不互相替代。包括 pending+error 的保护仍用原0e3c解析器。

逻辑调用 start/finish 与 HTTP attempt 是不同层次。独立工作线程进入 API 时建根调用，
不伪造跨线程父子。相同线程嵌套关联最内层；会话切换、被容量上限丢弃的内层或直接 HTTP
都明确记为未关联，绝不默认算给上一层。没有改变原有网络层/信号/最终flush顺序。
报告中的 dispatch_return 不是最终退出；process_exit/stdout_complete/stderr_complete
保持 null。被强制终止只有 start 时是未知，不声称成功取消或费用为0。

## 完整性和隐私

逻辑层最多保留512次，HTTP层沿用原512次。总计数、dropped、pending、记录错误均保留，
有缺项不能宣称整体记录完整。日志失败不重试 API、不替换已产生的函数返回；
外层 observe-model 会报告证据不完整。collector 单次会话使用，封存后的迟到完成不改
已有报告。不会持有观测锁执行 API、回调或网络；Writer 本身不得重入该收集器。

只写固定枚举、序号、时间、布尔和明确未知字段；不保存 prompt、reply、模型名、
endpoint、APIkey、错误正文/代码/类型/哈希或响应ID。时间和调用图仍可能敏感，
文件未加密，内存/文件删除不等于安全擦除。权限沿用原新目录工具限制；
不能把它当作敌对并发文件系统、恶意同进程代码、独立租户或模型账单认证。

## 验证

全部测试使用临时HOME、合成配置及数字回环服务，无用户脑库、付费提供方或客户端登录。
原0e3c sidecar及费用代码字节不变；新的生命周期、关联、并发、容量、日志错误、
真实子进程中断和闭管道、Windows真实调用均需绑定本分支新SHA。
Linux不开启PG，旧Windows专用N39测试不冒称在Linux执行；原rerank测试单独调用。
完整项目/真实PG/非作者结论/最终60-55步整合仍各自报告，不由计数自动关闭。
