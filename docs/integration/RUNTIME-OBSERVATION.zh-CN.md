# N48W 实际模型 HTTP 调用观测（未合并候选）

只在显式选择时记录同一进程进入 `http_post_json` 的尝试。没有开关时不生成报告；
缓存命中、本地 mock、没有凭据而未进入 HTTP 的调用不虚构为外发。其它进程、替代网络
库、供应商内部重试、内部工具和计费系统不在本观测范围内。不是全链路账单认证。

## 运行入口

`qbrain observe --output NEW_DIRECTORY -- EXISTING_COMMAND ...`

例如在已经明确授权的数据/提供方环境中，用新的输出目录包裹原来的 search、think
或 serve 命令。程序不会替你获取密钥、开启模型权限或安装客户端。原命令的 stdout、
stderr 和业务副作用仍遵循原命令，本模块只约束额外 sidecar，不是全程序日志脱敏器。
先用 `qbrain observe --output observation-demo -- help` 验证无外发的空观测。
目录必须不存在；不覆盖已有目录/文件。不应把输出目录放到共享或不可信位置。

`started.json` 标记观察开始；`attempts/N.start.json` 在尝试前创建，
`N.finish.json` 在返回后创建；最后写 `report.json`。观察到的状态包括完成HTTP、
HTTP错误、输入拒绝、网络失败、超时、明确取消、超出响应限额、平台不支持和本地异常。
进程被杀时，start无finish表示未完成/未知，不能宣称取消成功或费用为零。没有最终
report.json的目录不能直接用于最终计价。仅开始文件不能证明请求已经到达服务器。

只保存固定枚举、序号、HTTP状态、耗时和数量；不保存prompt、响应文本、模型名称、
URL、API key、响应ID或这些私密字符串的哈希。用量/时间本身也可能敏感，请保护报告。
文件未加密，内存或磁盘删除不是安全擦除。既有N48M新文件路径保护不是敌对并发文件
系统沙箱。Windows权限沿用父目录，Linux新目录限定拥有者；不要把它当作租户ACL。

最多保留512次尝试；更多调用仍按原逻辑执行，计数和dropped使完整性标志为false。
写日志失败不会替换模型结果或重试请求，但外层observe返回证据不完整错误。
mutex只保护记录，不围住网络调用。作用域结束时还没完成的工作会留下pending；
报告封存后迟到结果不改写它。这里只证明记录完整，不证明usage或业务回答完整。

## 用量与成本

原生Chat/Responses的用量映射复用N48G：缓存分桶缺失、矛盾、不识别、超限或重复JSON
键均保持未知，不把inclusive input当作uncached input。Embeddings只观察明确报告的
inclusive input/total，没有缓存桶证据时四个计价桶仍未知。通用rerank账单格式不猜。
非终态Responses的用量不用于最终计价。HTTP200不证明模型回答成功；terminal failed/
cancelled响应仍可保留已报告用量。非2xx响应体原来被传输层抑制，观测不为计价改变它。

每次重复进入边界都单独保留，但不能根据相同prompt或响应ID猜测重试关系。
`retry_attempts`、默认价格/货币和成本都是null。已知失败并不等于无账单。

离线入口：`qbrain observe cost --report report.json --assignments assignments.json`。
assignments schema为qbrain-observation-rates-v1，含currency、rates与assignments数组。
rates沿用原qbrain-cost-input-v1格式。每份assignment必须恰好给出sequence、call_id、
attempt、stage、rate_id；每条保留记录都必须分配，不能只挑成功/便宜的子集。它不能
覆盖tokens或outcome。没有完整记录/已知usage/适用费率时，顶层total_estimate仍null；
observed_record_cost只描述保留记录的已知小计与缺项，不代表整个业务总额。

模型名/端点没有留在观测中，因此提供方、模型、费率适用性、阶段和retry标签是操作者
的明确声明，未被自动认证。准确计算使用原N48F整数缩放算法，不重新实现浮点计价。
输出不含服务端工具费用、税、折扣或汇率转换，未知不能被解释为免费。读取/计价时
结构检查可发现不一致，但不能认证同时被伪造的原始观察数据；报告未签名。

## 验收边界

测试只使用合成数据、固定数值和数字回环HTTP服务器。未调用付费提供方、未进入用户
Windows客户端、未执行真实PG。显式OS取消由传输错误码识别；没有新增取消API。硬终止
和超时清理不能冒充成功取消。原生记录、新SHA和非作者审查分别关联，不挪用PR64结果。
PR61/62/63、d57验收及冻结的PG测试上传均不受本分支修改。无合并/部署/新运行包。
